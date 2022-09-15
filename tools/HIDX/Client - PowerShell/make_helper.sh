#!/bin/sh

(printf '//Stage 1 loader, gzip compressed and base64-encoded\nstage1="%s";\n' $(cat stage1.ps1 | gzip -9 -c | base64 -w 0); cat helper.tmpl ) > helper.js


