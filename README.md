# 😼 Criticat

**Status:** In Development

A GitHub Action for automated PDF document review using Gemini AI.

## Overview

Criticat reviews PDF documents for formatting issues and provides feedback as GitHub PR comments. It uses Google's Gemini 1.5 Flash model to analyze document layout and structure visually.

## Features

- 🔍 **Visual PDF Analysis**: Converts PDFs to images for layout analysis
- 🤖 **AI-Powered Reviews**: Uses Gemini 1.5 Flash to evaluate document formatting
- 💬 **PR Comments**: Automatically comments on PRs with detailed feedback
- 😺 **Customizable Jokes**: Adds sarcastic cat-themed jokes based on configuration

## Output

Criticat generates a JSON report (`criticat_feedback.json` by default) containing detailed feedback and any generated jokes. When run in a GitHub Actions context for a PR, it will post this feedback as a comment.

## Requirements

- Google Cloud project with Vertex AI API enabled
- GitHub repository with workflow permissions
- PDF documents to analyze

## Usage

### Configuration

Criticat uses `pydantic-settings` and can be configured via command-line arguments or environment variables. Key variables include:

- `CRITICAT_GCP_PROJECT_ID`: Your Google Cloud Project ID (required if `--project-id` not provided).
- `CRITICAT_GCP_LOCATION`: The GCP location for Vertex AI (defaults to `us-central1` if `--location` not provided).
- `CRITICAT_JOKE_MODE`: Sets the joke mode (`none`, `default`, `chaotic`). Defaults to `default`.

### CLI

```bash
gcloud auth application-default login
criticat --pdf-path "example.pdf" --project-id "my-project"
```

### Docker

First, build the Docker image:
```bash
docker build -t criticat .
```

Then, run the container, mounting your PDF directory and GCP credentials:
```bash
docker run \
  -v "/path/to/your/pdf/directory:/data" \
  -v "$HOME/.config/gcloud:/root/.config/gcloud" \
  criticat \
  --pdf-path "/data/your_document.pdf" \
  --project-id "your-gcp-project-id"
```
**Note:**
- Replace `/path/to/your/pdf/directory` with the actual path on your host machine containing the PDF.
- Replace `your_document.pdf` with the actual filename of your PDF. The path inside the container will start with `/data/`.
- Replace `your-gcp-project-id` with your Google Cloud project ID.
- The second `-v` mounts your local `gcloud` credentials (ADC) into the container. Adjust if you use a different authentication method (e.g., service account key).

### Server Modes (API & Protocol Access)

Besides the CLI, Criticat can run as a server, exposing its functionality through different protocols.

#### Standard FastAPI Server

This runs a standard FastAPI web server using Uvicorn, defined in `src/criticat/interfaces/api.py` (or similar). You can add standard REST API endpoints directly to this FastAPI application.

Start the server using the `criticat-api` command:
```bash
# Ensure GCP authentication is set up (e.g., gcloud auth application-default login)
criticat-api

# Or specify host and port
# criticat-api --host 0.0.0.0 --port 8080
```
The server will typically run on `http://127.0.0.1:8000`. Standard HTTP clients can interact with any REST endpoints defined in the application.

#### Model Context Protocol (SSE via FastAPI)

This protocol runs *on top of* the Standard FastAPI Server (started via `criticat-api`). It uses Server-Sent Events (SSE) over HTTP, typically served at the `/mcp` endpoint. This is the recommended way for MCP clients (like specific LLM frontends or agents) to interact with Criticat's tools over the network.

#### Model Context Protocol (stdio - Experimental/Limited)

This mode allows interaction via standard input/output, suitable for local process communication. **Note:** This transport currently has limitations within the underlying `fastapi-mcp` library and may not function as expected for tool calls.

Start the server using the `criticat-mcp` command:
```bash
# Ensure GCP authentication is set up
criticat-mcp
```
Clients would interact by sending JSON-RPC 2.0 messages to the process's stdin and reading responses from stdout. Due to the current limitations, using the SSE server or the CLI via `subprocess` is recommended for programmatic interaction.

### GitHub Actions (In Development)

```yaml
name: Review PDF Document

on:
  pull_request:
    paths:
      - '**/*.pdf'

jobs:
  review-pdf:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v2
        with:
          credentials_json: ${{ secrets.GCP_CREDENTIALS }}
      
      - name: Criticat PDF Review
        uses: your-org/criticat@v1
        with:
          pdf-path: ./path/to/document.pdf
          project-id: your-gcp-project-id
          joke-mode: default  # Options: none, default, chaotic
```

## Inputs

| Name | Description | Required | Default |
|------|-------------|----------|---------|
| `pdf-path` | Path to the PDF file to review | Yes | |
| `project-id` | Google Cloud project ID | Yes | |
| `location` | Google Cloud location for Vertex AI | No | `us-central1` |
| `github-token` | GitHub token for API access | No | `${{ github.token }}` |
| `repository` | GitHub repository (owner/repo) | No | `${{ github.repository }}` |
| `pr-number` | Pull request number | No | `${{ github.event.pull_request.number }}` |
| `joke-mode` | Mode for injecting cat jokes | No | `default` |

## Joke Modes

- `none`: No jokes in comments
- `default`: Add 1 joke if formatting issues are found
- `chaotic`: Add 1-3 jokes regardless of review outcome

## Architecture

Criticat's core logic is built using:
- LangChain + LangGraph for workflow orchestration
- Pydantic for configuration and state validation
- `pydantic-settings` for environment variable configuration
- Typer for CLI interface
- FastAPI for the API server
- `fastapi-mcp` for Model Context Protocol implementation (SSE & stdio)
- Vertex AI for LLM integration
- `dependency-injector` for managing internal dependencies

## Development

To set up the project for development:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/fardust/criticat.git
    cd criticat
    ```
2.  **Create a virtual environment:** (Using `uv` recommended)
    ```bash
    uv venv
    source .venv/bin/activate 
    # Or on Windows: .venv\Scripts\activate
    ```
3.  **Install dependencies:** (Including development/test extras)
    ```bash
    # Install editable base package
    uv sync --group dev --group test
    # Add development and test dependencies
    uv add --group dev ruff mypy pytest pytest-cov
    # Add any other specific dev/test dependencies here
    ```
4.  **Run tests:**
    ```bash
    uv run pytest
    ```
5.  **Run linters/formatters:** (Assuming Ruff and Mypy are configured)
    ```bash
    uv run ruff check .
    uv run ruff format .
    uv run mypy src/
    ```

## License

MIT