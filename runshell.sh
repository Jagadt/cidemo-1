#!/bin/bash
chmod 400 FARM-7-410c49e8.us-east-1.pem
scp -C -i FARM-7-410c49e8.us-east-1.pem -r * root@52.54.214.199:/var/www/html/
echo "build success"
