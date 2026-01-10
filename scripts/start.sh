#!/bin/bash
# Inventory Management Agent - Start Script
# Usage: ./scripts/start.sh [dev|prod|seed|test|setup]

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  Inventory Management Agent${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

check_env() {
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}⚠️  .env file not found. Creating from .env.example...${NC}"
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo -e "${YELLOW}📝 Please edit .env with your configuration (especially OPENAI_API_KEY)${NC}"
            exit 1
        else
            echo -e "${RED}❌ .env.example not found. Please create .env manually.${NC}"
            exit 1
        fi
    fi
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"
}

check_postgres() {
    if ! command -v psql &> /dev/null; then
        echo -e "${YELLOW}⚠️  PostgreSQL client not found. Make sure your database is accessible.${NC}"
    else
        echo -e "${GREEN}✓ PostgreSQL client available${NC}"
    fi
}

install_deps() {
    echo -e "${BLUE}📦 Installing dependencies...${NC}"
    pip install -e ".[dev]" --quiet
    echo -e "${GREEN}✓ Dependencies installed${NC}"
}

run_dev() {
    print_header
    check_env
    check_python
    
    echo -e "${BLUE}🚀 Starting development server...${NC}"
    echo -e "${GREEN}   API docs: http://localhost:8000/docs${NC}"
    echo -e "${GREEN}   Health:   http://localhost:8000/api/v1/health${NC}"
    echo ""
    
    python -m src.main
}

run_prod() {
    print_header
    check_env
    check_python
    
    echo -e "${BLUE}🚀 Starting production server...${NC}"
    
    uvicorn src.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 4 \
        --log-level info
}

run_seed() {
    print_header
    check_env
    check_python
    
    echo -e "${BLUE}🌱 Seeding database...${NC}"
    python scripts/seed_database.py
    echo -e "${GREEN}✓ Database seeded successfully${NC}"
}

run_tests() {
    print_header
    check_python
    
    echo -e "${BLUE}🧪 Running tests...${NC}"
    pytest tests/ -v --tb=short
}

run_setup() {
    print_header
    echo -e "${BLUE}🔧 Setting up project...${NC}"
    echo ""
    
    check_python
    check_postgres
    
    # Create .env if needed
    if [ ! -f ".env" ]; then
        echo -e "${YELLOW}Creating .env from template...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}⚠️  Edit .env with your OPENAI_API_KEY and database credentials${NC}"
    else
        echo -e "${GREEN}✓ .env exists${NC}"
    fi
    
    # Install dependencies
    install_deps
    
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Setup complete! Next steps:${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "  1. ${YELLOW}Edit .env${NC} with your OpenAI API key and database URL"
    echo ""
    echo -e "  2. ${YELLOW}Create PostgreSQL database:${NC}"
    echo -e "     createdb inventory_db"
    echo ""
    echo -e "  3. ${YELLOW}Seed the database:${NC}"
    echo -e "     ./scripts/start.sh seed"
    echo ""
    echo -e "  4. ${YELLOW}Start the server:${NC}"
    echo -e "     ./scripts/start.sh dev"
    echo ""
}

show_help() {
    print_header
    echo ""
    echo "Usage: ./scripts/start.sh [command]"
    echo ""
    echo "Commands:"
    echo "  setup    First-time project setup (install deps, create .env)"
    echo "  dev      Start development server with hot reload"
    echo "  prod     Start production server with multiple workers"
    echo "  seed     Seed database with sample data"
    echo "  test     Run test suite"
    echo "  help     Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/start.sh setup   # First time setup"
    echo "  ./scripts/start.sh dev     # Start dev server"
    echo "  ./scripts/start.sh seed    # Populate database"
    echo ""
}

# Main
case "${1:-help}" in
    dev)
        run_dev
        ;;
    prod)
        run_prod
        ;;
    seed)
        run_seed
        ;;
    test)
        run_tests
        ;;
    setup)
        run_setup
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
