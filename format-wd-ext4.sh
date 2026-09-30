#!/bin/bash
# One-time: wipe the WD 4TB Immich disk (NTFS, no partition table) and
# recreate it as a single ext4 partition mounted at /mnt/data.
# Preconditions (checked 2026-09-29): library verified identical on
# immich-backup and immich-backup2 (146,875 files, 1,494.3 GB).
# Run: sudo bash format-wd-ext4.sh
set -euo pipefail

DISK=/dev/disk/by-id/ata-WDC_WD40EZAZ-00SF3B0_WD-WX72D22ESR5C
OLD_UUID=29BC88E540B8CC84
MNT=/mnt/data
OWNER=jackwan

[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
[ -b "$DISK" ] || { echo "disk $DISK not found"; exit 1; }
echo "Target: $DISK -> $(readlink -f $DISK)"
lsblk -o NAME,SIZE,FSTYPE,LABEL,SERIAL,MOUNTPOINT "$DISK"

# Safety: both backups must be mounted and complete
for b in /media/$OWNER/immich-backup /media/$OWNER/immich-backup2; do
    n=$(find "$b/immich/library" -type f | wc -l)
    echo "backup $b: $n files"
    [ "$n" -ge 146875 ] || { echo "backup $b incomplete, aborting (nothing changed)"; exit 1; }
done
if fuser -m "$MNT" >/dev/null 2>&1; then fuser -vm "$MNT"; echo "$MNT is in use, aborting (nothing changed)"; exit 1; fi

read -r -p "Type ERASE to wipe the WD disk: " ans
[ "$ans" = ERASE ] || { echo "aborted"; exit 1; }

# 1. unmount and wipe
umount "$MNT"
wipefs -a "$DISK"

# 2. GPT + one partition, ext4 (1% reserved instead of 5%)
parted -s "$DISK" mklabel gpt mkpart immich-disk ext4 0% 100%
udevadm settle
mkfs.ext4 -F -L immich-disk -m 1 "${DISK}-part1"
udevadm settle
NEW_UUID=$(blkid -s UUID -o value "${DISK}-part1")
echo "new UUID: $NEW_UUID"

# 3. fstab: back up, replace the old NTFS line
cp /etc/fstab /etc/fstab.bak-ntfs-$(date +%Y%m%d)
sed -i "s|^UUID=\"$OLD_UUID\".*|UUID=$NEW_UUID  $MNT  ext4  defaults,noatime,nofail  0  2|" /etc/fstab
grep -n "$MNT" /etc/fstab
systemctl daemon-reload

# 4. mount and prepare Immich upload location
mount "$MNT"
mkdir -p "$MNT/immich"
chown -R "$OWNER:$OWNER" "$MNT"
findmnt "$MNT"
df -h "$MNT"
echo "DONE"
