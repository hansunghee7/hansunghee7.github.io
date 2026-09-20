#!/bin/bash
# 구PC 저소음 설정: 안 쓰는 회전식 하드 2개(sdb, sdc)를 1분 유휴 시 회전 정지시키고, 부팅 때마다 다시 적용한다.
# 실행: sudo bash ~/ops/quiet_setup.sh
# 되돌리기: sudo systemctl disable --now quiet-disks.service && sudo rm /etc/systemd/system/quiet-disks.service
set -e
D1=/dev/disk/by-id/ata-ST1000DM010-2EP102_Z9A7D6QL
D2=/dev/disk/by-id/ata-WDC_WD5000BEKT-22KA9T0_WD-WXA1A70E8296

cat > /etc/systemd/system/quiet-disks.service <<EOF
[Unit]
Description=Spin down unused HDDs (low noise)
After=local-fs.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=-/usr/sbin/hdparm -S 12 $D1 $D2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now quiet-disks.service
hdparm -y $D1 $D2 >/dev/null 2>&1 || true
sleep 3
echo "--- 결과(standby 이면 회전 정지) ---"
hdparm -C $D1 $D2
