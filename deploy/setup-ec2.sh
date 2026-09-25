#!/bin/bash
# =============================================================================
# EC2 Instance Setup Script — Movie Recommendation Engine
#
# Run this on a fresh Amazon Linux 2023 or Ubuntu 22.04 EC2 instance:
#   curl -sSL <raw-github-url>/deploy/setup-ec2.sh | bash
#
# Prerequisites:
#   - EC2 t3.micro instance (free tier)
#   - Security group: inbound 22 (SSH), 80 (HTTP), 443 (HTTPS)
#   - At least 20 GB EBS storage (default 8 GB is too small for Docker images)
# =============================================================================
set -euo pipefail

echo "=== Updating system ==="
sudo yum update -y 2>/dev/null || sudo apt-get update -y

echo "=== Installing Docker ==="
if ! command -v docker &>/dev/null; then
    # Amazon Linux 2023
    if [ -f /etc/amazon-linux-release ]; then
        sudo yum install -y docker
        sudo systemctl enable docker
        sudo systemctl start docker
        sudo usermod -aG docker $USER
    # Ubuntu
    else
        sudo apt-get install -y docker.io docker-compose-plugin
        sudo systemctl enable docker
        sudo systemctl start docker
        sudo usermod -aG docker $USER
    fi
fi

echo "=== Installing Docker Compose ==="
if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null; then
    COMPOSE_VERSION="v2.27.0"
    sudo mkdir -p /usr/local/lib/docker/cli-plugins
    sudo curl -SL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
    sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

echo "=== Installing Git ==="
sudo yum install -y git 2>/dev/null || sudo apt-get install -y git

echo "=== Cloning repository ==="
REPO_DIR="$HOME/movie-recommendation-engine"
if [ -d "$REPO_DIR" ]; then
    cd "$REPO_DIR" && git pull
else
    git clone https://github.com/Skywalker1910/movie-recommendation-engine.git "$REPO_DIR"
fi
cd "$REPO_DIR"

echo "=== Downloading dataset ==="
# The ML models and processed data need to be uploaded separately.
# You can SCP them or use the download script.
mkdir -p data/movielens models data_science/processed

echo ""
echo "=========================================="
echo " Setup complete!"
echo "=========================================="
echo ""
echo " Next steps:"
echo "  1. Upload ML models:    scp -r models/ ec2-user@<IP>:~/movie-recommendation-engine/"
echo "  2. Upload processed data: scp -r data_science/processed/ ec2-user@<IP>:~/movie-recommendation-engine/data_science/"
echo "  3. Upload dataset:      scp -r data/movielens/ ec2-user@<IP>:~/movie-recommendation-engine/data/"
echo "  4. Configure secrets:   nano movie_recommendation_system/backend/.env.production"
echo "  5. Generate secrets:    python3 -c \"import secrets; print(secrets.token_urlsafe(64))\""
echo "  6. Deploy:              cd movie_recommendation_system && docker compose -f docker-compose.prod.yml up -d --build"
echo "  7. Create admin:        docker compose -f docker-compose.prod.yml exec backend flask create-admin"
echo ""
echo " Your app will be at: http://<EC2-PUBLIC-IP>"
echo "=========================================="
