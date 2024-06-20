#!/bin/bash
echo "Running First Time Setup"
sudo apt-get update
sudo apt-get install python3-dev python3-pillow git python3-flask -y 
git clone https://github.com/hzeller/rpi-rgb-led-matrix.git
echo "Moving into rpi-rgb-led-matrix"
cd rpi-rgb-led-matrix || (echo "Did not download directory" && exit)
make build-python PYTHON=$(command -v python3)
sudo make install-python PYTHON=$(command -v python3)
ln -sf bindings/python ../rgbmatrix
cd ..
echo "Basic Setup Complete"
REBOOTNEEDED="false"
read -p "Add isolcpus=3 to /boot/firmware/cmdline.txt to improve display update speed? (y/N): " answer1
if [[ "$answer1" = "y" || "$answer1" = "Y" ]]; then
    echo "Adding"
    echo "isolcpus=3" >> /boot/firmware/cmdline.txt
    export REBOOTNEEDED="true"
else
    echo "Ok."
fi
echo "Disable audio drivers permanently?"
echo -e "\e[91mWARNING: This WILL overwrite your whole config.txt file.\e[0m\nExit This script and edit replacementConfig.txt to be consistent with what you already have configured"
echo "If you have not edited config.txt or do not know what this is, you may safely ignore the above warning"
read -p "Disable audio? (y/N): " answer2
if [[ "$answer2" = "y" || "$answer2" = "Y" ]]; then
    echo "Overwriting config.txt"
    cat replacementConfig.txt > /boot/firmware/config.txt
        export REBOOTNEEDED="true"
else
    echo "Ok."
fi
if [ "$REBOOTNEEDED" == "true" ]; then
    read -p "System needs to reboot for changes to be applied. reboot now? (Y/n): " answer3
    if [[ "$answer3" = "n" || "$answer3" = "N" ]]; then
        echo "Ok."
    else
        echo "Rebooting!"
        shutdown now --reboot
        sleep 90
    fi
fi
echo "Setup completed. Goodbye!"
exit