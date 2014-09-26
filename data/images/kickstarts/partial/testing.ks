
#
# Configure teh system to test the latest imgbased
#

# Build most recent imagbased for testing
%post --erroronfail
echo "Build imgbased"
yum install -y python-nose python-sh make git autoconf automake asciidoc yum-plugin-remove-with-leaves
yum remove -y imgbased || :

cd /root
git clone https://github.com/fabiand/imgbased.git
cd imgbased
./autogen.sh
./configure
make install
%end