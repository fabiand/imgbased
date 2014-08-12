

##
## Including ../partial/header.ks
##

#
# Header
#
lang en_US.UTF-8
keyboard us
timezone --utc Etc/UTC
auth --enableshadow --passalgo=sha512
selinux --enforcing
network --bootproto=dhcp
rootpw --plaintext r
firstboot --disable

reboot


clearpart --all --initlabel
bootloader --append="console=ttyS0" --timeout=1

part / --size=3096 --fstype=ext4 --label=Image-0.0 --fsoptions=discard


##
## Including ../partial/repositories.ks
##

#
# Repositories
#
url --mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-$releasever&arch=$basearch
#repo --name=fedora --mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=fedora-$releasever&arch=$basearch
repo --name=updates --mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=updates-released-f$releasever&arch=$basearch
#repo --name=updates-testing --mirrorlist=http://mirrors.fedoraproject.org/mirrorlist?repo=updates-testing-f$releasever&arch=$basearch

##
## Including ../partial/packages.ks
##

#
# Packages
#
%packages --excludedocs
@core

# In F21 --nocore is available, then we use this list
# to provide the minimal set of packages
#kernel
#systemd
#bash
#NetworkManager
#yum

# Only available in Fedora 20+
#anaconda-core
#anaconda-tui
#cockpit

vim-minimal
grub2-efi
shim
augeas

screen
#docker-io
#openvswitch

# Some things from @core we can do without inside the container
-biosdevname

%end


##
## Including ../partial/post.ks
##

#
# Add custom post scripts after the base post.
#
%post --erroronfail

# setup systemd to boot to the right runlevel
echo "Setting default runlevel to multiuser text mode"
rm -f /etc/systemd/system/default.target
ln -s /lib/systemd/system/multi-user.target /etc/systemd/system/default.target
echo .

#echo "Enable readonly-root"
#sed -i \
#    -e "s/^\(READONLY\)=.*/\1=yes/" \
#    -e "s/^\(TEMPORARY_STATE\)=.*/\1=yes/" \
#    /etc/sysconfig/readonly-root

#echo "Make rootfs ro"
# https://bugzilla.redhat.com/show_bug.cgi?id=1082085
#sed -i "s/subvol=Origin/subvol=Origin,ro/" /etc/fstab

#echo "Enable docker"
#systemctl enable docker.service || :

#echo "Enable openvswitch"
#systemctl enable openvswitch.service || :

#echo "Enable cockpit"
#systemctl enable cockpit.service || :

echo "Build imgbased"
pushd .
yum install -y make git autoconf automake
yum install -y asciidoc yum-plugin-remove-with-leaves
cd /root
git clone https://github.com/fabiand/imgbased.git
cd imgbased
./autogen.sh
make install
#yum remove -y --remove-leaves asciidoc
popd

echo "Install image-minimizer"
curl -O https://git.fedorahosted.org/cgit/lorax.git/plain/src/bin/image-minimizer
install -m775 image-minimizer /usr/bin

echo "Enable FDO Bootloader Spec"
echo "echo '# Import BLS entries'" > /etc/grub.d/42_bls
echo "echo bls_import" >> /etc/grub.d/42_bls
chmod a+x /etc/grub.d/42_bls

echo "Enable Syslinux  configuration"
echo "echo '# Import syslinux entries'" > /etc/grub.d/42_syslinux
echo "echo syslinux_configfile syslinux.cfg" >> /etc/grub.d/42_syslinux
chmod a+x /etc/grub.d/42_syslinux


# Update grub2 cfg
grub2-mkconfig -o /boot/grub2/grub.cfg
#grub2-mkconfig -o /boot/efi/EFI/fedora/grub.cfg

echo "Getty fixes"
# although we want console output going to the serial console, we don't
# actually have the opportunity to login there. FIX.
# we don't really need to auto-spawn _any_ gettys.
sed -i '/^#NAutoVTs=.*/ a\
NAutoVTs=0' /etc/systemd/logind.conf

echo "Fix missing console device"
/bin/mknod /dev/console c 5 1

echo "Cleaning old yum repodata."
yum clean all

echo "Fixing SELinux contexts."
touch /var/log/cron
touch /var/log/boot.log
mkdir -p /var/cache/yum

# have to install policycoreutils to run this... commenting for now
/usr/sbin/fixfiles -R -a restore

%end

##
## Including ../partial/minimization.ks
##

#
# Remove some stuff using image-minimizer
#
%post --nochroot --interpreter image-minimizer

# kernel modules minimization
drop /lib/modules/*/kernel/sound
drop /lib/modules/*/kernel/drivers/media
drop /lib/modules/*/kernel/net/wireless

drop /usr/share/zoneinfo
keep /usr/share/zoneinfo/UTC

drop /usr/share/awk
drop /usr/share/vim
drop /usr/src

# glibc-common locales
drop /usr/lib/locale
keep /usr/lib/locale/locale-archive
keep /usr/lib/locale/usr/share/locale/en_US

# docs
drop /usr/share/doc
drop /usr/share/locale/
keep /usr/share/locale/en_US
keep /usr/share/locale/zh_CN
drop /usr/share/man

# yum
drop /var/log/yum.log
drop /var/lib/yum/*
drop /var/cache/yum/*
drop /root/install.*
drop /root/anaconda.*
drop /var/log/anaconda*
%end

#
# Just run depmod because we messed with kernel modules
#
%post
depmod -a
%end
