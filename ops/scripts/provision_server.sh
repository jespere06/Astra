#!/bin/bash
set -e

# ==========================================
# CONFIGURACIÓN
# ==========================================
USER_NAME="astra"
SSH_PORT=2222
TIMEZONE="America/Bogota"
DATA_ROOT="/var/lib/astra/data"

# Colores
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}>>> Iniciando Provisionamiento de Servidor ASTRA...${NC}"

# 1. Actualización del Sistema
echo -e "${GREEN}[1/6] Actualizando paquetes y sistema...${NC}"
apt-get update && apt-get upgrade -y
apt-get install -y curl git ufw fail2ban htop unzip

# 2. Configuración de Zona Horaria
timedatectl set-timezone $TIMEZONE

# 3. Creación de Usuario (Deploy)
if id "$USER_NAME" &>/dev/null; then
    echo "Usuario $USER_NAME ya existe."
else
    echo -e "${GREEN}[2/6] Creando usuario $USER_NAME...${NC}"
    useradd -m -s /bin/bash $USER_NAME
    usermod -aG sudo $USER_NAME
    # Crear directorio SSH
    mkdir -p /home/$USER_NAME/.ssh
    chmod 700 /home/$USER_NAME/.ssh
    
    # Copiar llaves de root si existen (para no perder acceso)
    if [ -f /root/.ssh/authorized_keys ]; then
        cp /root/.ssh/authorized_keys /home/$USER_NAME/.ssh/
        chmod 600 /home/$USER_NAME/.ssh/authorized_keys
        chown -R $USER_NAME:$USER_NAME /home/$USER_NAME/.ssh
    fi
    
    # Configurar sudo sin contraseña (Opcional, útil para automatización CI/CD)
    echo "$USER_NAME ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-cloud-init-users
fi

# 4. Instalación de Docker y Docker Compose
if ! command -v docker &> /dev/null; then
    echo -e "${GREEN}[3/6] Instalando Docker...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    usermod -aG docker $USER_NAME
    rm get-docker.sh
else
    echo "Docker ya está instalado."
fi

# 5. Hardening SSH
echo -e "${GREEN}[4/6] Asegurando SSH...${NC}"
sed -i "s/#Port 22/Port $SSH_PORT/" /etc/ssh/sshd_config
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config

# 6. Configuración Firewall (UFW) y Fail2Ban
echo -e "${GREEN}[5/6] Configurando Firewall y Fail2Ban...${NC}"
ufw default deny incoming
ufw default allow outgoing
ufw allow $SSH_PORT/tcp  # SSH Custom
ufw allow 80/tcp         # HTTP (Traefik)
ufw allow 443/tcp        # HTTPS (Traefik)
# Nota: NO abrimos 5432, 6379, 6333, 9000, 9001. Quedan internos en Docker.

echo "y" | ufw enable

# Configurar Fail2Ban para el puerto custom
cat <<EOT > /etc/fail2ban/jail.local
[sshd]
enabled = true
port = $SSH_PORT
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
EOT
systemctl restart fail2ban

# 7. Preparación de Directorios de Persistencia
echo -e "${GREEN}[6/6] Creando directorios de datos...${NC}"
mkdir -p $DATA_ROOT/postgres
mkdir -p $DATA_ROOT/redis
mkdir -p $DATA_ROOT/qdrant
mkdir -p $DATA_ROOT/minio
mkdir -p $DATA_ROOT/traefik

# Asignar permisos (ajustar según GID de contenedores si es necesario, 
# por ahora root:root funciona para volumenes montados)
# chown -R 1001:1001 $DATA_ROOT # Ejemplo para Bitnami images

echo -e "${GREEN}>>> Provisionamiento Completado.${NC}"
echo "IMPORTANTE: SSH ahora corre en el puerto $SSH_PORT. No cierres esta sesión sin probar abrir otra terminal:"
echo "ssh -p $SSH_PORT $USER_NAME@<IP-DEL-SERVIDOR>"
systemctl restart sshd
