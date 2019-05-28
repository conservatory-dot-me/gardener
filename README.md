# Gardener

Gardener is an automated plant watering system powered by single board computer (SBC) with dashboard built using Django web framework.

![Desktop screenshot](gardener/dashboard/static/dashboard/img/screenshot-desktop.png?raw=true "Desktop screenshot")

Gardener (c) by conservator@conservatory.me

Gardener is licensed under a
Creative Commons Attribution-NonCommercial 4.0 International License.

You should have received a copy of the license along with this
work. If not, see <http://creativecommons.org/licenses/by-nc/4.0/>.

## Features

- Automatic hourly/3-hourly/daily/weekly/monthly watering schedule with watering duration based on local weather forecast.

- Start time for daily/weekly/monthly scheduled watering is set based on time of local sunrise.

- Receive an email notification when scheduled watering is started.

- Option to manually start/stop pump from web-based user interface.

- Option to manually start/stop pump from tactile switches on device.

- LED indicator on device to monitor current expected precipitation.

- 16x2 LCD on device to show its current private and public IP for web access.

- Option to remotely operate the pumps from anywhere in the world on your computer or mobile device.

- Automatic daily lighting schedule with adjustable lighting duration.

- Web-based admin interface.

## Django project setup

### Create project database

```
sudo su - postgres
psql
CREATE USER gardener WITH PASSWORD 'gardener';
CREATE DATABASE gardener;
GRANT ALL PRIVILEGES ON DATABASE gardener TO gardener;
ALTER ROLE gardener CREATEDB;
\q
exit
```

### Setup and run project

```
./run.sh
```
### Running project tests

```
venv/bin/pytest
```

## Adding new device

To setup a new device, add the device and its associated location in the admin page.
Currently, only one active device is supported.
In order to get weather forecasts, location must have a weather forecast provider.
If a new weather forecast provider is required, a new method must be implemented in update_weather_forecast.py.
Refer to the existing method `get_bom_gov_au_weather_forecasts` as an example.

## Single board computer (SBC) setup

The SBC of choice in this documentation is ODROID-C2. Most of the steps described below can be applied to most SBCs with little or no modification.

Download the latest base image from https://wiki.odroid.com/odroid-c2/os_images/ubuntu/minimal_image and follow the steps below to reimage the eMMC module.

Plug eMMC module to its reader and insert into a Linux-based host computer.

Run the command below to find the device name for the eMMC module.

```
dmesg
```

You should see something like below in your `dmesg` output.

```
[294648.576071]  sdb: sdb1 sdb2
```

Run the commands below to write the image into the eMMC module. `sdb` MUST be replaced with the right value based on your `dmesg` output above.

```
sudo umount /dev/sdb1
sudo umount /dev/sdb2

sudo dd if=ubuntu-18.04-3.16-minimal-odroid-c2-20180626.img of=/dev/sdb bs=1M
sync
sync
sync
```

Eject eMMC module and mount it on ODROID-C2.

Connect UART cable, Ethernet cable and ODROID WiFI module 0 to ODROID-C2 and power it up. Wait for blue LED to turn off (red LED should remain on) and power it off and on again for the disk resize operation to take effect.

Generate the SSH keypair on host computer for use to login as `gardener` into ODROID-C2 later.

```
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa_gardener -C id_rsa_gardener
```

Login into ODROID-C2 from host computer using `sudo minicom -s`. See https://wiki.odroid.com/accessory/development/usb_uart_kit for minicom setup.

Username: root
Password: odroid

Remove root password using the command below.

```
passwd -dl root
```

Run the commands below to setup the system. Manual instructions are shown in angle brackets e.g. `<Instruction here>`.

```
apt -y update && apt -y upgrade && apt -y dist-upgrade && apt -y autoremove && apt -y clean && apt -y update

sed -i 's/#LoginGraceTime 2m/LoginGraceTime 3/g' /etc/ssh/sshd_config
sed -i 's/PermitRootLogin yes/PermitRootLogin no/g' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/g' /etc/ssh/sshd_config
sed -i 's/#Port 22/Port 51438/g' /etc/ssh/sshd_config

rm /etc/ssh/ssh_host* && dpkg-reconfigure openssh-server
<Select "keep the local version currently installed">

dd if=/dev/zero of=/root/swapfile bs=512 count=1048576 && chmod 600 /root/swapfile && mkswap /root/swapfile && swapon /root/swapfile

cat << EOF > /etc/fstab
LABEL=boot                                      /media/boot vfat    defaults,rw,owner,flush,umask=000   0   0
UUID=e139ce78-9841-40fe-8823-96a304a09859       /           ext4    errors=remount-ro,noatime           0   1
/root/swapfile                                  swap        swap    defaults                            0   0
EOF

mount -a

echo "gardener" > /etc/hostname

addgroup gpio
adduser gardener && usermod -a -G gpio,sys,video,sudo gardener
<Enter password for user gardener>

cat << EOF > /etc/udev/rules.d/90-odroid-sysfs.rules 
SUBSYSTEM=="gpio", KERNEL=="gpiochip*", ACTION=="add", PROGRAM="/bin/sh -c 'chown root:gpio /sys/class/gpio/export /sys/class/gpio/unexport ; chmod 220 /sys/class/gpio/export /sys/class/gpio/unexport'"
SUBSYSTEM=="gpio", KERNEL=="gpio*", ACTION=="add", PROGRAM="/bin/sh -c 'chown root:gpio /sys%p/active_low /sys%p/direction /sys%p/edge /sys%p/value ; chmod 660 /sys%p/active_low /sys%p/direction /sys%p/edge /sys%p/value'"
EOF

udevadm control --reload-rules && udevadm trigger

echo -e "\nblacklist w1_gpio" >> /etc/modprobe.d/blacklist.conf && update-initramfs -u

apt install -y \
    build-essential \
    cmake \
    curl \
    git-core \
    htop \
    libbz2-dev \
    liblzma-dev \
    libncurses5-dev \
    libncursesw5-dev \
    libpq-dev \
    libreadline-dev \
    libsqlite3-dev \
    libssl-dev \
    llvm \
    man-db \
    net-tools \
    nginx \
    postgresql \
    redis-server \
    rng-tools \
    rsync \
    tk-dev \
    unattended-upgrades \
    zlib1g-dev

sed -i 's/notify-keyspace-events ""/notify-keyspace-events KEg$shzx/g' /etc/redis/redis.conf
service redis-server restart

locale-gen "en_US.UTF-8"
dpkg-reconfigure locales
<Select Ok on first screen, select "en_US.UTF-8" on second screen and select Ok>

update-alternatives --config editor
<Select 7 for vim>

visudo
gardener ALL=(ALL) NOPASSWD:ALL

su - gardener
mkdir ~/.ssh
echo "<Paste content of ~/.ssh/id_rsa_gardener.pub from host computer here>" > ~/.ssh/authorized_keys

git clone https://github.com/hardkernel/wiringPi
cd wiringPi
sudo ./build

exit

nmcli d wifi list
<Look for your WiFi SSID>

nmcli dev wifi con "<Your WiFi SSID>" password <Your WiFi password> name "<Your WiFi SSID>"

reboot
```

Login into ODROID-C2 over WiFi as normal user.

```
ssh -p 51438 -i ~/.ssh/id_rsa_gardener gardener@<ODROID-C2 wlan0 IP address>
```

Install pyenv to manage Python installation.

```
git clone https://github.com/pyenv/pyenv.git ~/.pyenv
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.profile
echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.profile
echo -e 'if command -v pyenv 1>/dev/null 2>&1; then\n  eval "$(pyenv init -)"\nfi' >> ~/.profile
source ~/.profile
pyenv install 3.7.3 && echo 'export PYENV_VERSION=3.7.3' >> ~/.profile && source ~/.profile
pip install --upgrade pip
pip install numpy
```

Install OpenCV.

```
git clone https://github.com/opencv/opencv
cd opencv
mkdir build && cd build
cmake -DBUILD_EXAMPLES=OFF -DBUILD_DOCS=OFF -DBUILD_PERF_TESTS=OFF -DBUILD_TESTS=OFF -DENABLE_PRECOMPILED_HEADERS=OFF -DBUILD_opencv_apps=OFF -DBUILD_opencv_calib3d=OFF -DBUILD_opencv_dnn=OFF -DBUILD_opencv_features2d=OFF -DBUILD_opencv_flann=OFF -DBUILD_opencv_gapi=OFF -DBUILD_opencv_highgui=OFF -DBUILD_opencv_java_bindings_generator=OFF -DBUILD_opencv_ml=OFF -DBUILD_opencv_objdetect=OFF -DBUILD_opencv_stitching=OFF -DBUILD_opencv_ts=OFF -DPYTHON_INCLUDE_DIR=$PYENV_ROOT/versions/3.7.3/include/python3.7m -DPYTHON_LIBRARY=$PYENV_ROOT/versions/3.7.3/lib -DOPENCV_PYTHON_INSTALL_PATH=$HOME/opencv/build ..
make -j4
sudo make install
sudo ldconfig
python python_loader/setup.py develop
```

The following GPIO pins on ODROID-C2 are selected for the default configuration.

- Pump
    - Export GPIO# 229
    - WiringPI #10
    - 16x2 LCD pin P5 CE0

- Light
    - Export GPIO# 230
    - WiringPI #14
    - 16x2 LCD pin P5 SCLK

See the "Django project setup" section above to complete the setup.
