#!/bin/bash
# ACIS demo host bootstrap (Debian 12 on AWS, eu-west-1; runs once at first boot as root).
# The OS layer only (owner ruling 2026-10-01, "Hybrid, on AWS"):
# - the SSM agent: the host takes no SSH, control is SSM and the owner's shell is Session Manager;
# - the `acis` user with NO sudo, which runs both the watchdog and the practice engine;
# - /etc/acis and /var/lib/acis owned by `acis`, 700 (the owner's secrets land there, 600);
# - a firewall rule keeping `acis` processes off the instance metadata service: the instance
#   role's credentials are for the SSM agent, never for the engine or the watchdog.
# The code, the venv and the watchdog unit arrive later by deploy/aws/acis-demo-prepare.sh.
set -euxo pipefail
exec > >(tee -a /var/log/acis-bootstrap.log) 2>&1
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git tmux python3-venv nftables
curl -fsSL -o /tmp/amazon-ssm-agent.deb \
  https://s3.eu-west-1.amazonaws.com/amazon-ssm-eu-west-1/latest/debian_amd64/amazon-ssm-agent.deb
dpkg -i /tmp/amazon-ssm-agent.deb
systemctl enable --now amazon-ssm-agent

id acis || useradd --create-home --shell /bin/bash acis
install -d -m 755 -o acis -g acis /opt/acis
install -d -m 700 -o acis -g acis /etc/acis /var/lib/acis

cat > /etc/nftables.conf <<'NFT'
#!/usr/sbin/nft -f
flush ruleset
table inet acis_imds {
  chain output {
    type filter hook output priority 0; policy accept;
    ip daddr 169.254.169.254 meta skuid "acis" reject
  }
}
NFT
systemctl enable nftables
systemctl restart nftables

touch /var/tmp/acis-bootstrap-done
