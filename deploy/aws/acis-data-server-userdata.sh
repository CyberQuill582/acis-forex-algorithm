#!/bin/bash
# ACIS data server bootstrap (Amazon Linux 2023, runs once at first boot as root).
# Installs Python 3.11 + git and mounts the separate data disk at /data. The data
# disk survives instance termination, so it is formatted ONLY if it has no filesystem.
set -euxo pipefail
exec > >(tee -a /var/log/acis-bootstrap.log) 2>&1

dnf install -y python3.11 git

ROOT_DISK="/dev/$(lsblk -no PKNAME "$(findmnt -no SOURCE /)")"
DATA_DISK=""
for d in $(lsblk -dpno NAME,TYPE | awk '$2=="disk"{print $1}'); do
  [ "$d" = "$ROOT_DISK" ] && continue
  DATA_DISK="$d"
  break
done
[ -n "$DATA_DISK" ]

blkid "$DATA_DISK" || mkfs.xfs -L acisdata "$DATA_DISK"
mkdir -p /data
grep -q 'LABEL=acisdata' /etc/fstab || echo 'LABEL=acisdata /data xfs defaults,nofail 0 2' >> /etc/fstab
mount -a
mkdir -p /data/acis
chown ec2-user:ec2-user /data/acis

touch /var/tmp/acis-bootstrap-done
