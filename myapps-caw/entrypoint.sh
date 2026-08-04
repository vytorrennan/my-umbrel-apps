#!/usr/bin/env bash
set -e

# Ensure Oh My Zsh and theme exist on the persistent volume
if [ ! -d "/home/developer/.oh-my-zsh" ]; then
  echo "Installing Oh My Zsh on developer home volume..."
  su - developer -c '
    git clone --depth=1 https://github.com/ohmyzsh/ohmyzsh.git ~/.oh-my-zsh || true
    git clone --depth=1 https://github.com/zsh-users/zsh-autosuggestions ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions || true
    git clone --depth=1 https://github.com/zsh-users/zsh-syntax-highlighting ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting || true
    git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ~/.oh-my-zsh/custom/themes/powerlevel10k || true
  '
fi

# Always update / restore .zshrc and .p10k.zsh if missing or unconfigured
if [ ! -f "/home/developer/.p10k.zsh" ] || ! grep -q "powerlevel10k" /home/developer/.zshrc 2>/dev/null; then
  echo "Deploying .zshrc and .p10k.zsh configurations..."
  cp /etc/skel/.zshrc /home/developer/.zshrc 2>/dev/null || true
  cp /etc/skel/.p10k.zsh /home/developer/.p10k.zsh 2>/dev/null || true
fi

# Ensure developer user owns /home/developer
chown -R developer:developer /home/developer 2>/dev/null || true

# Start Caw as developer user in /home/developer
echo "Starting Caw on port 8080..."
exec su - developer -c 'export HOST=0.0.0.0; export PORT=8080; export TERM=xterm-256color; cd /home/developer; exec /usr/local/bin/caw'
