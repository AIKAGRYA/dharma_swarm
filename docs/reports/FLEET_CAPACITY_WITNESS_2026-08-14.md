# Fleet Capacity Witness — 2026-08-14 JST

**Document class:** `witness`. This file preserves one read-only observation;
it owns no role, capacity, liveness, or cleanup decision. SSH aliases identify
routes used for the probe, not durable node identities. Re-run before acting.

**Replaces:** none. **Subordinate to:** the future ratified node/profile capacity
owner and any newer probe witness.

## Probe

The operator Mac ran this command at `2026-08-13T23:41:36Z`
(`2026-08-14T08:41:36+09:00`) while the inspected repository checkout was at
`de52bef55adcbb9193c839288b7bb827eb1176b8`:

```bash
date -u '+captured_at_utc=%Y-%m-%dT%H:%M:%SZ'
git rev-parse HEAD
for fleet_alias in agni rushabdev meghadharma; do
  echo "alias=${fleet_alias}"
  ssh -o BatchMode=yes -o ConnectTimeout=8 "$fleet_alias" \
    'set -u; printf "hostname="; hostname; \
     printf "kernel="; uname -srm; \
     printf "root_df="; df -Pk / | tail -1; \
     printf "root_inode="; df -Pi / | tail -1; \
     printf "memory="; free -b | awk '\''/^Mem:/ {print $0}'\''; \
     printf "uptime="; uptime; exit 0'
  echo "ssh_exit=$?"
done
printf 'mac_hostname='; hostname
printf 'mac_kernel='; uname -srm
printf 'mac_data_df='; df -Pk /Users/dhyana | tail -1
printf 'mac_data_inode='; df -Pi /Users/dhyana | tail -1
printf 'rush_mirror='; ssh -o BatchMode=yes -o ConnectTimeout=8 rushabdev \
  'du -skx /home/openclaw/dhyana_mirror 2>/dev/null; \
   stat -c "mtime=%y" /home/openclaw/dhyana_mirror 2>/dev/null; \
   for n in rsync rclone syncthing; do \
     pgrep -a "$n" 2>/dev/null || true
   done'
echo "rush_mirror_exit=$?"
printf 'mac_mirror='; \
  du -sk /Users/dhyana/vps_mirrors/rushabdev_dhyana_mirror
echo "mac_mirror_exit=$?"
```

## Captured visible output

```text
captured_at_utc=2026-08-13T23:41:36Z
de52bef55adcbb9193c839288b7bb827eb1176b8
alias=agni
hostname=agni-openclaw
kernel=Linux 6.8.0-101-generic x86_64
root_df=/dev/vda1        120791536 99881228  20893924      83% /
root_inode=/dev/vda1      15597568 1588179 14009389   11% /
memory=Mem:      8326946816  3557863424  1754640384     3469312  3339640832  4769083392
uptime= 23:41:36 up 38 days, 11:20,  5 users,  load average: 0.61, 0.89, 0.92
ssh_exit=0
alias=rushabdev
hostname=openclaw23onubuntu-s-2vcpu-4gb-120gb-intel-sgp1-01
kernel=Linux 6.8.0-136-generic x86_64
root_df=/dev/vda1        120791536 119910560    864592     100% /
root_inode=/dev/vda1      15597568 1421322 14176246   10% /
memory=Mem:      4106100736  1592905728   659341312     3497984  2162589696  2513195008
uptime= 23:41:38 up 23 days, 13:59,  2 users,  load average: 0.09, 0.11, 0.07
ssh_exit=0
alias=meghadharma
hostname=meghadharma-cloud
kernel=Linux 6.8.0-136-generic x86_64
root_df=/dev/vda1        120791536 79321124  41454028      66% /
root_inode=/dev/vda1      15597568 1768620 13828948   12% /
memory=Mem:      4106100736  2631704576   202604544     3362816  1593016320  1474396160
uptime= 23:41:39 up 23 days,  8:36,  9 users,  load average: 6.28, 6.34, 6.26
ssh_exit=0
mac_hostname=Johns-MacBook-Pro.local
mac_kernel=Darwin 25.5.0 arm64
mac_data_df=/dev/disk3s5  1948404040 1476058288 444921100    77%    /System/Volumes/Data
mac_data_inode=/dev/disk3s5 3896808080 2952116576 889842200    77% 17618059 4449211000    0%   /System/Volumes/Data
rush_mirror=35708632	/home/openclaw/dhyana_mirror
mtime=2026-07-21 13:00:29.739344339 +0000
rush_mirror_exit=0
mac_mirror=35672392	/Users/dhyana/vps_mirrors/rushabdev_dhyana_mirror
mac_mirror_exit=0
```

## Interpretation limits

- All three SSH scripts and both mirror-size command groups returned zero. The
  main remote script explicitly ended with `exit 0`, so that proves route/script
  completion, not independent success of every inner command. Every expected
  capacity field was populated.
- The process loop returned no matching `rsync`, `rclone`, or `syncthing`
  process at that instant. Its errors and missing-path errors were redirected,
  so the capture is not complete stderr; it did not inspect systemd, cron,
  timers, tmux, launchd, containers, or remote push jobs.
- `df` and `du` are point observations. They do not prove ownership,
  recoverability, filesystem health, object equality, or permission to delete.
- The probe did not establish provider instance identity, disk latency/type,
  firewall posture, service health, broker topology, backup freshness, or
  writer eligibility.
- Meghadharma's load average was elevated during this sample. Placement needs a
  longer host-readiness observation, not this one reading.
