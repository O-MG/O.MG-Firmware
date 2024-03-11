import os
import re
import random

class FileHelper:

    @staticmethod
    def read_file_to_list(file_path):
        try:
            with open(file_path, 'r') as file:
                # Read the lines from the file and strip newline characters
                lines = [line.strip() for line in file]
            return lines
        except FileNotFoundError:
            print(f"The file {file_path} was not found.")
            return []
        except IOError:
            print(f"An error occurred while reading the file {file_path}.")
            return []
            
    @staticmethod
    def get_text_file_names(directory):
        text_file_names = [os.path.splitext(f)[0] for f in os.listdir(directory) if f.endswith('.txt')]
        return text_file_names
    
class MacGenerator:
    
    def __init__(self, directory=""):
        self.directory = directory
        self.manufacturer = ''

    def generate(self, mac_prefix=''):
        required_octets = 3
        if mac_prefix:
            if isinstance(mac_prefix, list):
                mac_prefix = random.choice(mac_prefix)
            if not isinstance(mac_prefix, str) or not self.valid_mac_address(mac_prefix, True):
                raise ValueError('Invalid mac prefix')
        else:
            required_octets = 6

        generated_octets = ':'.join([f"{random.randint(0, 255):02x}" for _ in range(required_octets)])

        if required_octets == 3:
            mac_address = mac_prefix + ':' + generated_octets
        else:
            mac_address = generated_octets
        
        if not self.valid_mac_address(mac_address):
            raise ValueError('Invalid mac address')
        
        return mac_address.upper()

    def valid_mac_address(self, mac, affix=False):
        mac_regex = {
            'half': r'^([0-9A-Fa-f]{2}:){2}[0-9A-Fa-f]{2}$',
            'full': r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        }
        if affix:
            valid = re.match(mac_regex['half'], mac)
        else:
            valid = re.match(mac_regex['full'], mac)
        return valid
        
    def get_manufacturer_prefixes(self, manufacturer, directory=""):
        self._ensure_directory(directory)
        try:
            filePath = f"{self.directory}/{manufacturer}.txt"
            mac_prefixes = FileHelper.read_file_to_list(filePath)
            if len(mac_prefixes) < 1:
                raise ValueError("Manufacturer prefix file empty")
        except:
            raise FileExistsError('Manufacturer prefix file not found')
        return self.format_prefixes(mac_prefixes)
    
    def _ensure_directory(self, directory=""):
        if directory and not self.directory:
            self.directory = directory
        if not directory and not self.directory:
            raise ValueError("Manufacturer prefix file not specified")
        
    def get_manufacturers(self, directory=""):
        self._ensure_directory(directory)
        self.manufacturers = FileHelper.get_text_file_names(self.directory)
        return self.manufacturers

    def format_prefixes(self, mac_prefix_list):
        formatted_mac_prefix_list = []
        for mac_prefix in mac_prefix_list:
            valid_prefix = self.valid_mac_address(mac_prefix, True)
            if not valid_prefix:
                formatted_mac_prefix = f"{mac_prefix[:2]}:{mac_prefix[2:4]}:{mac_prefix[4:]}"
            elif valid_prefix:
                formatted_mac_prefix = mac_prefix
            else:
                continue
            formatted_mac_prefix_list.append(formatted_mac_prefix)
        return formatted_mac_prefix_list
    
if __name__ == "__main__":
    #run from root dir or change string if it fails for now

    mac_generator = MacGenerator('./mac-prefixes')
    manufacturers = mac_generator.get_manufacturers()
    print("\n".join(manufacturers))
    try:
        manufacturer_prefixes = mac_generator.get_manufacturer_prefixes("apple")
        mac_address = mac_generator.generate(manufacturer_prefixes)
        print(f"Generated mac: {mac_address}")
    except Exception as error:
        print(f"An error occurred: {error}")
        
    #print("Generated mac address:", mac_address)


#https://www.coffer.com/mac_find/
#chrome-extension://mbigbapnjcgaffohmbkdlecaccepngjd
#//tr[not(td[2][contains(., '('))])]/td[1]
