#!/usr/bin/env bash
# ==============================================================================
# Playlink All-in-One Launcher Script
# Launches the unified Playlink appliance container (Postgres + Backend + Frontend + Cloudflare)
# ==============================================================================

set -e

# Default values
CONTAINER_NAME="playlink"
IMAGE_NAME="playlink-allinone:latest"
DATA_VOLUME="playlink_pgdata"
POSTGRES_USER="playlink"
POSTGRES_DB="playlink"
POSTGRES_PASSWORD=""
JWT_SECRET=""
CLOUDFLARE_TUNNEL_TOKEN=""
ORIGIN=""
PUBLIC_BACKEND_URL=""
PUBLIC_WS_URL=""
ADMIN_ADDRESSES=""
EXPOSE_PORTS=false
SINGLE_DOMAIN=false
DO_BUILD=false
ACTION="run"
ENV_FILE=".env.playlink"
SAVE_ENV=false

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------

print_help() {
    cat << 'EOF'
Playlink All-in-One Appliance Launcher

Usage:
  ./run-playlink.sh [OPTIONS]

Options:
  -t, --cloudflare-token <TOKEN>  Cloudflare Tunnel Token (from Zero Trust dashboard)
  -o, --origin <URL>              Frontend public Origin URL (e.g. https://playlink.domain.com)
  -b, --public-backend <HOST|URL> Backend domain or URL (e.g. playlink-backend.domain.com)
  -s, --jwt-secret <SECRET>       Secret for JWT tokens (auto-generated if omitted)
  -p, --postgres-password <PASS>  PostgreSQL password (auto-generated if omitted)
  -u, --postgres-user <USER>      PostgreSQL username (default: playlink)
  -d, --postgres-db <DB>          PostgreSQL database name (default: playlink)
  -a, --admin-addresses <ADDRS>   Comma-separated admin Ethereum addresses
  -v, --data-volume <NAME|PATH>   Docker volume name or host path for DB storage (default: playlink_pgdata)
  -n, --name <NAME>               Docker container name (default: playlink)
  -i, --image <IMAGE>             Docker image tag (default: playlink-allinone:latest)
      --single-domain             Route both frontend & backend through one domain (no public api subdomain)
      --expose-ports              Map ports 3000 and 8000 to host (useful for local access)
      --build                     Build the Docker image locally before running
      --env-file <PATH>           Path to env file to load defaults from (default: .env.playlink)
      --save-env                  Save entered configuration to .env.playlink for future runs
      --stop                      Stop and remove the running container
      --restart                   Restart the container
      --logs                      Follow container logs
  -h, --help                      Show this help message

Examples:
  # Run with Cloudflare Tunnel:
  ./run-playlink.sh -t "eyJh..." -o "https://playlink.bartek.monster" -b "playlink-backend.bartek.monster"

  # Run locally with exposed ports and interactive prompts:
  ./run-playlink.sh --build --expose-ports

  # Stop running container:
  ./run-playlink.sh --stop
EOF
}

generate_secret() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
    elif [ -r /dev/urandom ]; then
        head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
    else
        date +%s%N | sha256sum | head -c 64
    fi
}

clean_cloudflare_token() {
    local raw="$1"
    raw=$(echo "$raw" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e "s/^['\"]//" -e "s/['\"]$//")
    if echo "$raw" | grep -q -- '--token'; then
        raw=$(echo "$raw" | sed -E 's/.*--token[[:space:]=]+//')
    elif echo "$raw" | grep -q 'service install'; then
        raw=$(echo "$raw" | sed -E 's/.*service install[[:space:]]+//')
    fi
    raw=$(echo "$raw" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e "s/^['\"]//" -e "s/['\"]$//")
    echo "$raw"
}

# ------------------------------------------------------------------------------
# Load existing env file if present
# ------------------------------------------------------------------------------
if [ -f "$ENV_FILE" ]; then
    echo "Loading existing configuration from $ENV_FILE..."
    # shellcheck disable=SC1090
    . "$ENV_FILE"
elif [ -f ".env" ]; then
    echo "Loading existing configuration from .env..."
    # shellcheck disable=SC1091
    . ".env"
fi

# ------------------------------------------------------------------------------
# Parse Command Line Arguments
# ------------------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        -t|--cloudflare-token)
            CLOUDFLARE_TUNNEL_TOKEN="$2"
            shift 2
            ;;
        -o|--origin)
            ORIGIN="$2"
            shift 2
            ;;
        -b|--public-backend)
            PUBLIC_BACKEND_URL="$2"
            shift 2
            ;;
        -s|--jwt-secret)
            JWT_SECRET="$2"
            shift 2
            ;;
        -p|--postgres-password)
            POSTGRES_PASSWORD="$2"
            shift 2
            ;;
        -u|--postgres-user)
            POSTGRES_USER="$2"
            shift 2
            ;;
        -d|--postgres-db)
            POSTGRES_DB="$2"
            shift 2
            ;;
        -a|--admin-addresses)
            ADMIN_ADDRESSES="$2"
            shift 2
            ;;
        -v|--data-volume)
            DATA_VOLUME="$2"
            shift 2
            ;;
        -n|--name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -i|--image)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --single-domain)
            SINGLE_DOMAIN=true
            shift
            ;;
        --expose-ports)
            EXPOSE_PORTS=true
            shift
            ;;
        --build)
            DO_BUILD=true
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            if [ -f "$ENV_FILE" ]; then
                . "$ENV_FILE"
            fi
            shift 2
            ;;
        --save-env)
            SAVE_ENV=true
            shift
            ;;
        --stop)
            ACTION="stop"
            shift
            ;;
        --restart)
            ACTION="restart"
            shift
            ;;
        --logs)
            ACTION="logs"
            shift
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run './run-playlink.sh --help' for usage."
            exit 1
            ;;
    esac
done

# ------------------------------------------------------------------------------
# Handle Secondary Actions (Stop, Restart, Logs)
# ------------------------------------------------------------------------------
if [ "$ACTION" = "stop" ]; then
    echo "Stopping container '$CONTAINER_NAME'..."
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
    echo "Container '$CONTAINER_NAME' stopped."
    exit 0
fi

if [ "$ACTION" = "logs" ]; then
    exec docker logs -f "$CONTAINER_NAME"
fi

if [ "$ACTION" = "restart" ]; then
    echo "Restarting container '$CONTAINER_NAME'..."
    docker restart "$CONTAINER_NAME"
    exit 0
fi

# ------------------------------------------------------------------------------
# Check Docker Availability
# ------------------------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    echo "Error: docker command not found. Please install Docker."
    exit 1
fi

# ------------------------------------------------------------------------------
# Interactive Prompts (if values missing and running in interactive terminal)
# ------------------------------------------------------------------------------
if [ -t 0 ] && [ -z "$CLOUDFLARE_TUNNEL_TOKEN" ] && [ "$EXPOSE_PORTS" = false ]; then
    echo ""
    echo "=== Playlink Setup Wizard ==="
    echo "Enter your Cloudflare Tunnel Token (leave empty to run locally on host ports):"
    printf "Cloudflare Tunnel Token: "
    read -r input_token
    if [ -n "$input_token" ]; then
        CLOUDFLARE_TUNNEL_TOKEN="$input_token"
    else
        echo "No tunnel token entered. Ports 3000 and 8000 will be exposed locally."
        EXPOSE_PORTS=true
    fi
fi

# Sanitize and validate Cloudflare Tunnel Token if provided
if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    CLEANED=$(clean_cloudflare_token "$CLOUDFLARE_TUNNEL_TOKEN")
    if [ "$CLEANED" != "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
        echo "Note: Cleaned and extracted Cloudflare token from input."
        CLOUDFLARE_TUNNEL_TOKEN="$CLEANED"
    fi
    if [ "${#CLOUDFLARE_TUNNEL_TOKEN}" -eq 36 ] && echo "$CLOUDFLARE_TUNNEL_TOKEN" | grep -qE '^[0-9a-fA-F-]{36}$'; then
        echo ""
        echo "WARNING: The value passed for Cloudflare token ($CLOUDFLARE_TUNNEL_TOKEN) looks like a Tunnel UUID, NOT a Tunnel Token!"
        echo "In Cloudflare Zero Trust (Networks -> Tunnels), copy the base64 token string starting with 'eyJh...'."
        echo ""
    elif [[ ! "$CLOUDFLARE_TUNNEL_TOKEN" =~ ^eyJh ]]; then
        echo "Note: Cloudflare Tunnel tokens typically start with 'eyJh...'. Prefix provided: '${CLOUDFLARE_TUNNEL_TOKEN:0:8}...'"
    fi
fi

# Prompt for Origin if not set
if [ -t 0 ] && [ -z "$ORIGIN" ]; then
    if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
        printf "Public Frontend URL (Origin, e.g. https://playlink.bartek.monster): "
        read -r input_origin
        ORIGIN="${input_origin:-http://localhost:3000}"
    else
        ORIGIN="http://localhost:3000"
    fi
fi

# Format Backend URLs
ORIGIN="${ORIGIN:-http://localhost:3000}"

if [ "$SINGLE_DOMAIN" = true ]; then
    PUBLIC_BACKEND_URL="$ORIGIN"
    PUBLIC_WS_URL=$(echo "$ORIGIN" | sed -E 's|^http://|ws://|' | sed -E 's|^https://|wss://|')
elif [ -z "$PUBLIC_BACKEND_URL" ]; then
    if [[ "$ORIGIN" =~ ^https?://localhost(:[0-9]+)?$ ]]; then
        PUBLIC_BACKEND_URL="http://localhost:8000"
        PUBLIC_WS_URL="ws://localhost:8000"
    elif [[ "$ORIGIN" =~ https?://playlink\.(.*) ]]; then
        # Default to playlink-backend.<domain> (standard Playlink topology)
        DOMAIN_REST="${BASH_REMATCH[1]}"
        PUBLIC_BACKEND_URL="https://playlink-backend.$DOMAIN_REST"
        PUBLIC_WS_URL="wss://playlink-backend.$DOMAIN_REST"
    else
        # Guess api.<domain> if origin is provided
        HOST_PART=$(echo "$ORIGIN" | sed -E 's|^https?://||' | sed -E 's|:[0-9]+$||')
        PUBLIC_BACKEND_URL="https://api.$HOST_PART"
        PUBLIC_WS_URL="wss://api.$HOST_PART"
    fi
else
    # Normalize backend URL to include protocol if missing
    if [[ ! "$PUBLIC_BACKEND_URL" =~ ^https?:// ]]; then
        if [[ "$ORIGIN" =~ ^https:// ]]; then
            PUBLIC_BACKEND_URL="https://$PUBLIC_BACKEND_URL"
        else
            PUBLIC_BACKEND_URL="http://$PUBLIC_BACKEND_URL"
        fi
    fi
    # Derive WebSocket URL
    PUBLIC_WS_URL=$(echo "$PUBLIC_BACKEND_URL" | sed -E 's|^http://|ws://|' | sed -E 's|^https://|wss://|')
fi

# Generate secrets if missing
if [ -z "$JWT_SECRET" ]; then
    JWT_SECRET=$(generate_secret)
fi

if [ -z "$POSTGRES_PASSWORD" ]; then
    POSTGRES_PASSWORD=$(generate_secret)
fi

# ------------------------------------------------------------------------------
# Save config if requested
# ------------------------------------------------------------------------------
if [ "$SAVE_ENV" = true ]; then
    echo "Saving configuration to $ENV_FILE..."
    cat > "$ENV_FILE" << EOF
CLOUDFLARE_TUNNEL_TOKEN="$CLOUDFLARE_TUNNEL_TOKEN"
ORIGIN="$ORIGIN"
PUBLIC_BACKEND_URL="$PUBLIC_BACKEND_URL"
PUBLIC_WS_URL="$PUBLIC_WS_URL"
JWT_SECRET="$JWT_SECRET"
POSTGRES_USER="$POSTGRES_USER"
POSTGRES_PASSWORD="$POSTGRES_PASSWORD"
POSTGRES_DB="$POSTGRES_DB"
ADMIN_ADDRESSES="$ADMIN_ADDRESSES"
DATA_VOLUME="$DATA_VOLUME"
EOF
fi

# ------------------------------------------------------------------------------
# Build Image if requested
# ------------------------------------------------------------------------------
if [ "$DO_BUILD" = true ] || ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo ""
    echo "Building Docker image '$IMAGE_NAME' from Dockerfile.allinone..."
    DOCKER_BUILDKIT=1 docker build -f Dockerfile.allinone -t "$IMAGE_NAME" .
fi

# ------------------------------------------------------------------------------
# Run Container
# ------------------------------------------------------------------------------
echo ""
echo "Stopping existing '$CONTAINER_NAME' container if present..."
docker stop "$CONTAINER_NAME" 2>/dev/null || true
docker rm "$CONTAINER_NAME" 2>/dev/null || true

# Assemble Docker run arguments
DOCKER_ARGS=(
    "run" "-d"
    "--name" "$CONTAINER_NAME"
    "--restart" "unless-stopped"
    "-v" "$DATA_VOLUME:/var/lib/postgresql/data"
    "-e" "POSTGRES_USER=$POSTGRES_USER"
    "-e" "POSTGRES_PASSWORD=$POSTGRES_PASSWORD"
    "-e" "POSTGRES_DB=$POSTGRES_DB"
    "-e" "JWT_SECRET=$JWT_SECRET"
    "-e" "ORIGIN=$ORIGIN"
    "-e" "PUBLIC_BACKEND_URL=$PUBLIC_BACKEND_URL"
    "-e" "PUBLIC_WS_URL=$PUBLIC_WS_URL"
    "-e" "ADMIN_ADDRESSES=$ADMIN_ADDRESSES"
)

if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    DOCKER_ARGS+=("-e" "CLOUDFLARE_TUNNEL_TOKEN=$CLOUDFLARE_TUNNEL_TOKEN")
fi

if [ "$EXPOSE_PORTS" = true ]; then
    DOCKER_ARGS+=("-p" "3000:3000" "-p" "8000:8000")
fi

DOCKER_ARGS+=("$IMAGE_NAME")

echo "Starting Playlink appliance container..."
docker "${DOCKER_ARGS[@]}"

echo ""
echo "=== Playlink container started successfully! ==="
echo "Container Name : $CONTAINER_NAME"
echo "Image          : $IMAGE_NAME"
echo "Data Volume    : $DATA_VOLUME"
echo "Origin URL     : $ORIGIN"
echo "Backend URL    : $PUBLIC_BACKEND_URL"
echo "WebSocket URL  : $PUBLIC_WS_URL"
if [ -n "$CLOUDFLARE_TUNNEL_TOKEN" ]; then
    echo "Cloudflare     : Active (routing managed via Cloudflare Zero Trust)"
fi
if [ "$EXPOSE_PORTS" = true ]; then
    echo "Local Ports    : Frontend http://localhost:3000 | Backend http://localhost:8000"
fi
echo ""
echo "Useful commands:"
echo "  Follow logs : ./run-playlink.sh --logs (or: docker logs -f $CONTAINER_NAME)"
echo "  Stop stack  : ./run-playlink.sh --stop"
echo "  Restart     : ./run-playlink.sh --restart"
echo "================================================"
