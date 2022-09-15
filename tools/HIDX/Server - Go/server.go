package main

import (
	"encoding/hex"
	"fmt"
	"io"
	"net"
	"os"
	"time"
)

const (
	// SYN flag
	SYN = 1
	// ACK flag
	ACK = 2
	// FIN flag
	FIN = 4
	// RST flag
	RST = 8
)

// Packet represents a packet of data read or written to the generic HID interface
type Packet struct {
	seq     byte
	ack     byte
	channel byte
	flags   byte
	length  byte
	data    []byte
}

func (p *Packet) setSeq(seq byte) {
	p.seq = seq & 0x0F
}

func (p *Packet) getSeq() byte {
	return p.seq
}

func (p *Packet) setAck(ack byte) {
	p.ack = ack & 0x0F
}

func (p *Packet) getAck() byte {
	return p.ack
}

func (p *Packet) setChannel(channel byte) {
	p.channel = channel
}

func (p *Packet) getChannel() byte {
	return p.channel
}

func (p *Packet) setFlags(flags byte) {
	p.flags = flags
}

func (p *Packet) getFlags() byte {
	return p.flags
}

func (p *Packet) getLength() byte {
	return p.length
}

func (p *Packet) setData(data []byte) {
	p.length = byte(len(data))
}

func (p *Packet) getData() []byte {
	return p.data
}

func (p *Packet) getBytes(packetSize int) []byte {
	b := make([]byte, packetSize)
	b[0] = (p.seq << 4) | (p.ack)
	b[1] = p.getChannel()
	b[2] = p.getFlags()
	b[3] = p.length
	copy(b[4:4+len(p.data)], p.data)
	return b
}

func newPacket(b []byte) *Packet {
	return &Packet{seq: seq(b[0]), ack: ack(b[0]), channel: b[1], flags: b[2], length: b[3], data: b[4 : 4+b[3]]}
}

// Transport represents a potentially lossy transport
type Transport struct {
	txQueue         chan *Packet
	seqAckQ         chan byte
	newChannelQueue chan byte
	packetSize      int
	headerSize      int

	device io.ReadWriteCloser

	// the maximum number of unacknowledged packets in flight at any time
	maxPipeline byte
	// holds unacknowledged packets for retransmission (eventually)
	packets []*Packet
	// the last sequence number received from the other end
	lastRxSeq byte
	// the last ack number received from the other end
	lastRxAck byte
	// the last ack number we sent to the other end
	lastTxAck byte
	// the current transmit sequence number
	txSeq byte

	channels [256]*transportChannel
}

func sa(seq, ack byte) byte {
	return ((seq << 4) & 0xF0) & (ack & 0x0F)
}

func seq(sa byte) byte {
	return (sa >> 4)
}

func ack(sa byte) byte {
	return sa & 0x0F
}

func incr16(v byte) byte {
	return (v + 1) & 0x0F
}

func decr16(v byte) byte {
	return (v - 1) & 0x0F
}

func (t *Transport) reset() {
	for i, channel := range t.channels {
		t.channels[i] = nil
		if channel != nil {
			channel.closeQuietly()
		}
	}
	for {
		var b bool = false
		select {
		case ack := <-t.seqAckQ:
			fmt.Printf("Drained %d from seqAckQ\n", ack)
		case p := <-t.txQueue:
			fmt.Printf("Drained %v from txQueue\n", p)
		default:
			b = true
		}
		if b {
			break
		}
	}
	for i := range t.packets {
		t.packets[i] = nil
	}
	t.lastRxSeq = 0xFF
	t.lastRxAck = 0xFF
	t.txSeq = 4
}

func (t *Transport) getChannel(c byte) io.ReadWriteCloser {
	return t.channels[c]
}

func (t *Transport) getNewChannelQueue() <-chan byte {
	return t.newChannelQueue
}

func (t *Transport) start() {
	go t.reader()
	go t.writer()
}

func (t *Transport) reader() {
	fmt.Println("READ routine in progress")
	t.reset()
	var lastRead time.Time
	for {
		b := make([]byte, t.packetSize)
		n, err := t.device.Read(b)
		check(err)
		if n != t.packetSize {
			panic("Short Read!")
		}
		if time.Since(lastRead) > 2*time.Second {
			fmt.Printf("Synchronizing, last read was at %v\n", lastRead)
			t.reset()
		}
		lastRead = time.Now()

		t.debugPacket("RX:", b)

		p := newPacket(b[0:n])

		// first packet after reset, synchronizing
		if t.lastRxSeq == 0xFF {
			t.lastRxSeq = p.getSeq()
			// fmt.Printf("Resetting lastRxSeq to %02x\n", t.lastRxSeq)
		} else {
			if p.getSeq() == ((t.lastRxSeq + 1) & 0x0F) {
				t.lastRxSeq = p.getSeq()
			} else {
				fmt.Printf("Incorrect packet sequence no received %x, expected %x\n", p.getSeq(), t.lastRxSeq)
			}
		}

		// first packet after reset, synchronizing
		if t.lastRxAck == 0xFF {
			t.lastRxAck = (t.txSeq - 1) & 0x0F
			// fmt.Printf("Resetting lastRxAck to %02x\n", t.lastRxAck)
		} else {
			if p.getAck() == ((t.lastRxAck + 1) & 0x0F) {
				// fmt.Printf("Received ACK for seq %d, clearing history\n", p.getAck())
				t.packets[p.getAck()%t.maxPipeline] = nil
				t.lastRxAck = p.getAck()
			} else if p.getAck() == t.lastRxAck {
				// fmt.Println("ACK == LASTACK")
				// do nothing
			} else {
				fmt.Printf("Incorrect packet ack no received %x, lastRxAck is %x\n", p.getAck(), t.lastRxAck)
				// out of sequence!
			}
		}

		t.handleIncomingPacket(p)
		t.seqAckQ <- p.getSeq()
	}

}

func (t *Transport) submitTX(packet *Packet) {
	t.txQueue <- packet
}

func (t *Transport) handleIncomingPacket(p *Packet) {
	flags := p.flags
	channel := p.channel
	switch {
	case (flags & (SYN | ACK)) == (SYN | ACK):
		// ignore
		break
	case (flags & SYN) == SYN:
		if t.channels[channel] != nil {
			// Retransmit? Ignore it!
			break
		}
		fmt.Printf("Making new transport channel %d\n", channel)
		t.channels[channel] = t.newTransportChannel(channel)
		t.newChannelQueue <- channel
		t.txQueue <- &Packet{channel: channel, flags: flags | ACK}
		break
	case (flags & (RST | ACK)) == (RST | ACK):
	case (flags & (FIN | ACK)) == (FIN | ACK):
		t.channels[channel] = nil
		break
	case (flags & RST) == FIN:
	case (flags & FIN) == FIN:
		if t.channels[channel].rxBuffer != nil {
			close(t.channels[channel].rxBuffer)
			t.channels[channel].rxBuffer = nil
		}
		t.txQueue <- &Packet{channel: channel, flags: flags | ACK}
		break
	case (flags & ACK) == ACK:
		if t.channels[channel] == nil {
			fmt.Printf("Received ACK for closed channel %d, flags were %02x, sending RST\n", channel, flags)
			t.txQueue <- &Packet{channel: channel, flags: RST}
			return
		}
		if p.length > 0 {
			t.channels[channel].rxBuffer <- p.data
		}
		break
	case flags == 0 && channel == 0 && p.length == 0:
		break
	default:
		fmt.Printf("Unexpected packet received on channel %d, flags %02x, length %d", p.channel, p.flags, p.length)
	}
}

func (t *Transport) getTransmitPacket() (byte, *Packet, error) {
	var packet *Packet = nil
	var ack byte = t.lastTxAck
	var more bool

	// fmt.Println("Waiting for TX or ACK")
	select {
	case packet, more = <-t.txQueue:
		if !more {
			return ack, nil, io.EOF
		}
		break
	case ack, more = <-t.seqAckQ:
		if !more {
			return ack, nil, io.EOF
		}
		break
	}
	// we got one value, now check non-blocking for the other
	if packet != nil {
		select {
		case ack = <-t.seqAckQ:
		default:
		}
	} else {
		select {
		case packet = <-t.txQueue:
		default:
		}
	}
	if packet == nil {
		b := make([]byte, t.packetSize)
		packet = newPacket(b)
	}
	return ack, packet, nil
}

func (t *Transport) debugPacket(prefix string, b []byte) {
	// if p.getFlags() != 0 || p.getLength() != 0 {
	fmt.Printf("%s\n%s", prefix, hex.Dump(b[0:15]))
	// }
}

func (t *Transport) writer() {
	fmt.Println("WRITE routine in progress")
	var maxPipeline = byte(len(t.packets))

	for {
		var ack byte
		var err error
		var packet *Packet = nil

		if t.packets[t.txSeq%maxPipeline] != nil {
			// fmt.Printf("Waiting for a slot for seq %x", t.txSeq)
			for t.packets[t.txSeq%maxPipeline] != nil {
				time.Sleep(10 * time.Millisecond)
				// fmt.Print(".")
			}
			// fmt.Println()
		}

		ack, packet, err = t.getTransmitPacket()
		if err == io.EOF {
			return
		}
		t.packets[t.txSeq%maxPipeline] = packet

		packet.setSeq(t.txSeq)
		packet.setAck(ack)
		t.lastTxAck = ack

		t.debugPacket("TX:", packet.getBytes(t.packetSize))

		var n int
		n, err = t.device.Write(packet.getBytes(t.packetSize))
		check(err)
		if n < t.packetSize {
			panic(fmt.Sprintf("Short write to device! %d < %d", n, t.packetSize))
		}
		t.txSeq = (t.txSeq + 1) & 0x0F
		// time.Sleep(100 * time.Millisecond)
	}
}

func (t *Transport) newTransportChannel(channel byte) *transportChannel {
	rxBuffer := make(chan []byte, 16)
	return &transportChannel{transport: t, channel: channel, rxBuffer: rxBuffer, partialRead: nil}
}

func newTransport(device io.ReadWriteCloser, packetSize int, maxPending byte) Transport {
	t := Transport{device: device}
	t.packetSize = packetSize
	t.headerSize = 4
	t.txQueue = make(chan *Packet, maxPending)
	t.seqAckQ = make(chan byte, maxPending)
	t.newChannelQueue = make(chan byte, 256)

	t.maxPipeline = 16
	t.packets = make([]*Packet, t.maxPipeline)

	t.reset()
	return t
}

// transportChannel defines a channel multiplexed over a Transport
type transportChannel struct {
	transport   *Transport
	channel     byte
	rxBuffer    chan []byte
	partialRead []byte
}

func (tc *transportChannel) Read(b []byte) (int, error) {
	var c []byte
	if tc.partialRead != nil {
		c = tc.partialRead
	} else {
		cx, more := <-tc.rxBuffer
		if !more {
			return 0, io.EOF
		}
		c = cx
	}
	n := copy(b, c)
	if n < len(c) {
		tc.partialRead = c[n:]
	} else {
		tc.partialRead = nil
	}
	return n, nil
}

// Writes at max Transport.packetSize - Transport.headerSize bytes from the
// provided byte array over the multiplexed Transport
func (tc *transportChannel) Write(b []byte) (int, error) {
	var m = min(tc.transport.packetSize-tc.transport.headerSize, len(b))
	var c = make([]byte, m)
	n := copy(c, b)
	tc.transport.txQueue <- &Packet{channel: tc.channel, flags: ACK, length: byte(n), data: c}
	return n, nil
}

func (tc *transportChannel) closeQuietly() {
	if tc.rxBuffer != nil {
		close(tc.rxBuffer)
		tc.rxBuffer = nil
	}
}

func (tc *transportChannel) Close() error {
	tc.closeQuietly()
	tc.transport.txQueue <- &Packet{channel: tc.channel, flags: FIN}
	return nil
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// Reading files requires checking most calls for errors.
// This helper will streamline our error checks below.
func check(e error) {
	if e != nil {
		panic(e)
	}
}

func relay(reader io.ReadCloser, writer io.WriteCloser) error {
	b := make([]byte, 1024)
	for {
		n, err := reader.Read(b)
		if err != nil {
			writer.Close()
			fmt.Printf("Error %v\n", err)
			return err
		}
		// fmt.Printf("Read %d bytes\n", n)
		var s int = 0
		var w int
		if n > 0 {
			for {
				w, err = writer.Write(b[s:n])
				if err != nil {
					fmt.Printf("Error %v\n", err)
				}
				if w > 0 {
					// fmt.Printf("Wrote %d bytes\n", w)
				} else {
					// fmt.Println("Wrote 0 bytes, exiting")
					reader.Close()
					return io.EOF
				}
				s += w
				if s == n {
					break
				}
				// time.Sleep(3 * time.Second)
			}
		}
	}
}

func join(a io.ReadWriteCloser, b io.ReadWriteCloser) {
	go relay(a, b)
	go relay(b, a)
}

func main() {
	hidPath := "/dev/hidg2"
	f, err := os.OpenFile(hidPath, os.O_RDWR, 0600)
	check(err)

	fmt.Println("main started")
	transport := newTransport(f, 64, 16)
	transport.start()
	channelQueue := transport.getNewChannelQueue()
	for {
		c := <-channelQueue
		fmt.Printf("Channel %d opened\n", c)
		tc := transport.getChannel(c)
		var conn io.ReadWriteCloser = nil
		var err error
		switch c {
		case 0:
			conn, err = os.Open("../../Client/PowerShell/Proxy.ps1")
			break
		case 1:
			conn, err = net.Dial("tcp", "localhost:4444")
			break
		default:
			conn, err = net.Dial("tcp", "localhost:65535")
		}
		if err != nil {
			fmt.Printf("Error opening channel %d: %v\n", c, err)
			tc.Close()
		} else {
			join(tc, conn)
		}
	}
}
