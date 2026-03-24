# Playlink - Moduł Sumatywny

Playlink is a full-stack application providing secure, non-custodial identity management. The system is built with a FastAPI backend, a SvelteKit frontend, and a PostgreSQL database, orchestrated via Docker Compose.

**Project Kanban:** [GitHub Project Board](https://github.com/orgs/ioad-modul-sumatywny-26/projects/2)

## Access

Frontend and backend are available at:  
[frontend](https://playlink.bartek.monster/)
[backend documentation](https://playlink-backend.bartek.monster/docs)

## Deployment

Changes merged into the `main` branch are automatically deployed. The deployment process typically takes between 30 seconds and 5 minutes to complete, depending on the scope and complexity of the changes..

## Technical Architecture

| Component      | Technology             | Management |
| -------------- | ---------------------- | ---------- |
| Frontend       | SvelteKit (TypeScript) | Bun        |
| Backend        | FastAPI (Python)       | uv         |
| Database       | PostgreSQL 18          | Docker     |
| ORM            | SQLModel               | —          |
| Authentication | BIP39 Identity / ECDSA | ethers.js  |
| Git Hooks      | prek                   | uv         |

### Identity Authentication Flow

The application utilizes a non-custodial challenge-response mechanism based on BIP39 and ECDSA signatures:

1. **Local Derivation:** The client derives a cryptographic identity from a 12-word mnemonic phrase locally; the private key never leaves the client environment.
2. **Challenge Generation:** The backend issues a unique, one-time random nonce (challenge).
3. **Cryptographic Proof:** The client signs the challenge using the derived private key.
4. **Session Verification:** The backend verifies the signature against the nonce and issues a JSON Web Token (JWT).

Detailed specifications are available in `backend/docs/auth-flow.md`.

## Project Organization

- `backend/`: API services, database models, and authentication logic.
- `frontend/`: SvelteKit application and identity management UI.
- `prezentacje/`: Project documentation and presentation materials.
- `docker-compose.yml`: Multi-container orchestration configuration.
