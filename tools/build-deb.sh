#!/usr/bin/env bash
set -euo pipefail

version="$1"
executable="$2"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_root="$root/dist/deb-root"
package_name="serial-vision_${version}_amd64"

rm -rf "$package_root"
install -d "$package_root/DEBIAN" "$package_root/usr/bin" "$package_root/usr/lib/serial-vision"
cp -a "$executable/." "$package_root/usr/lib/serial-vision/"
chmod 0755 "$package_root/usr/lib/serial-vision/SerialVision"
ln -s ../lib/serial-vision/SerialVision "$package_root/usr/bin/serial-vision"

cat > "$package_root/DEBIAN/control" <<EOF
Package: serial-vision
Version: $version
Section: utils
Priority: optional
Architecture: amd64
Maintainer: homeandriy
Description: Serial Vision equipment serial number recognition utility
EOF

dpkg-deb --build --root-owner-group "$package_root" "$root/dist/$package_name.deb"
