# Steps to prepare new ubuntu server node (physical) to cluster

### 1. make user superuser (sudo)

```bash
sudo usermod -aG sudo {username}

# optional
groups username

# verify
sudo whoami
```

### 2. Install & setup Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh

sudo tailscale up

tailscale status

tailscale ip -4
```


### 3. Install & setup SSH

On the server:

```bash
# install
sudo apt update
sudo apt install openssh-server -y

# enable
sudo systemctl enable --now ssh

# check status
sudo systemctl status ssh
```

From remote machine:
```bash
# create key
ssh-keygen -t ed25519 -f /path/to/your/directory/your_key_name -C "your_email@example.com"
ssh-add /path/to/your/directory/your_key_name

# optional: view key
cat /path/to/your/directory/your_key_name.pub

# add to server
ssh-copy-id -i /path/to/your/directory/your_key_name.pub {username}@{server_ip}
```

On the server, edit ssh config:

```bash
sudo nano /etc/ssh/sshd_config
```
Make the following edits:
- Port 22
- Port 2222
- PubkeyAuthentication yes
- AuthorizedKeysFile	.ssh/authorized_keys .ssh/authorized_keys2
- PasswordAuthentication no

Test and apply changes:
```bash
sudo sshd -t
# Option A: Ubuntu 22.04 LTS and Older (Standard Service)
sudo systemctl reload ssh

# Option B: Ubuntu 24.04 LTS and Newer (Socket Activation)
sudo systemctl daemon-reload
sudo systemctl restart ssh.socket
```


### 4. Setup Static IP on Local Network

Get ethernet name
```bash
#find ethernet:
sudo ip a # look for something like "eno1" or "enp1s0": something that starts with 2
```

Edit `/etc/netplan/00-installer-config.yaml`:

```yaml
# This is the network config written by 'subiquity'
network:
  version: 2
  renderer: networkd
  ethernets:
    {ethernetName}:
      match:
        macaddress: {macAddress}
      set-name: {ethernetName}
      dhcp4: true
      dhcp6: true
      addresses:
        # static IP cidr; e.g
        # - 10.0.0.253/24
      routes:
        - to: default
            # put network gateway
          via: 10.0.0.1
      nameservers:
        addresses:
            # network gateway name servers
          - 1.1.1.1
          - 8.8.8.8

```

### 5. Add node to cluster

On the control plane node:
```bash
# print token
sudo cat /var/lib/rancher/k3s/server/node-token
```

One new node:
```bash
CONTROL_PLANE_IP=
CONTROL_PLANE_TOKEN=

curl -sfL https://get.k3s.io | K3S_URL=https://$CONTROL_PLANE_IP:6443 K3S_TOKEN=$CONTROL_PLANE_TOKEN sh -
```