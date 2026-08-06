# Docker Desktop And WSL2 Maintenance

Maintain Docker Desktop, WSL2, and Rancher Desktop for local development environments.

## Scope

This skill covers Docker Desktop troubleshooting, WSL2 disk compaction, port forwarding, Hyper-V issues, and common
maintenance tasks.

## Common Maintenance Tasks

### .vhdx Disk Compaction (WSL2)

WSL2 virtual disks grow over time and need manual compaction:

```powershell
# 1. Shutdown WSL
wsl --shutdown

# 2. Find the VHDX file (usually at %USERPROFILE%\AppData\Local\Packages\...\ext4.vhdx)
# 3. Compact using diskpart
diskpart
select vdisk file="C:\Users\{user}\AppData\Local\Packages\...\ext4.vhdx"
attach vdisk readonly
compact vdisk
detach vdisk
exit
```

### Port Forwarding (WSL2 → Windows)

WSL2 IPs change on reboot. Use port proxy rules:

```powershell
# Add port forwarding from Windows host to WSL2
netsh interface portproxy add v4tov4 \
  listenaddress=0.0.0.0 listenport=8080 \
  connectaddress={wsl-ip} connectport=8080

# View existing rules
netsh interface portproxy show all

# Remove rules
netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=8080
```

### Docker Desktop Troubleshooting

| Symptom | Likely Fix |
|---|---|
| Docker daemon not starting | `Settings → Troubleshoot → Reset to factory defaults` |
| K8s cluster not starting | Disable/re-enable K8s in Docker Desktop Settings |
| Disk space full | `docker system prune -a --volumes` |
| Network issues | Restart WSL: `wsl --shutdown && wsl` |
| Hyper-V conflict | Disable other hypervisors (VMware, VirtualBox) |

### Hyper-V Issues

Check Hyper-V services:

```powershell
Get-Service -Name *hyper* | Select-Object Name, Status

# Enable if disabled
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
```

## References

- K8s MCP: `kubernetes` server in `.vscode/mcp.json`
- Docker Compose → K8s: `kompose convert`
- CLI helpers: `python -m tools.sdd_cli environment-lab setup-lab`
