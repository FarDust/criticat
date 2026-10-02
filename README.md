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

This runs a standard FastAPI web server using Uvicorn, defined in `src/criticat/interfaces/api.py`. It exposes `POST /review` and `GET /health`.

Start the server using the `criticat-api` command:
```bash
# Ensure GCP authentication is set up (e.g., gcloud auth application-default login)
criticat-api

# Or specify host and port
# criticat-api --host 0.0.0.0 --port 8080
```
The server runs on `http://0.0.0.0:8000` by default (configurable with `CRITICAT_SERVER_HOST` / `CRITICAT_SERVER_PORT`). `POST /review` returns 400 for invalid input (missing project, missing or non-PDF file), 422 for schema errors and 500 if the review pipeline fails.

#### Model Context Protocol (SSE via FastAPI)

This protocol runs *on top of* the Standard FastAPI Server (started via `criticat-api`). It uses Server-Sent Events (SSE) at `/mcp` and exposes the REST operations as the MCP tools `review_pdf` and `health_check`. Tool calls are dispatched in-process to the FastAPI app, so no extra HTTP hop is needed.

#### Model Context Protocol (stdio / SSE - standalone server)

`criticat-mcp` runs a dedicated MCP server (built on the official MCP Python SDK). It speaks stdio by default, which is what desktop MCP clients such as Claude Desktop, Cursor or Windsurf expect. All logs go to stderr so stdout only carries protocol messages.

```bash
# stdio (default)
criticat-mcp

# SSE over HTTP
criticat-mcp --transport sse --host 127.0.0.1 --port 8000
```

| Option | Environment variable | Default |
| --- | --- | --- |
| `--transport {stdio,sse}` | `CRITICAT_MCP_TRANSPORT` | `stdio` |
| `--host` / `--port` (SSE only) | `CRITICAT_SERVER_HOST` / `CRITICAT_SERVER_PORT` | `0.0.0.0` / `8000` |
| `--log-level` | `CRITICAT_LOG_LEVEL` | `INFO` |

The GCP project is resolved from the `project_id` argument, then `CRITICAT_GCP_PROJECT_ID`, `CLOUDSDK_CORE_PROJECT` and `GOOGLE_CLOUD_PROJECT`. The location is resolved from the `location` argument, then `CRITICAT_GCP_LOCATION`, `CLOUDSDK_COMPUTE_REGION`, and finally `us-central1`.

Example client configuration (Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "criticat": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/FarDust/criticat", "criticat-mcp"],
      "env": { "CRITICAT_GCP_PROJECT_ID": "your-gcp-project-id" }
    }
  }
}
```

**Tools**

| Tool | Description |
| --- | --- |
| `review_pdf(pdf_path, project_id?, location?, joke_mode?, include_markdown?)` | Runs the Gemini review. Returns a summary (issue counts by severity, blocking flag), structured per-provider feedback, jokes and a Markdown report. Reports progress while it runs. |
| `validate_pdf(pdf_path)` | Cheap check that the file exists, is a real PDF and can be parsed. Returns the size and page count. Makes no Vertex AI calls. |
| `check_configuration()` | Reports the resolved project and location, whether Poppler is installed, and any problems that would make `review_pdf` fail. |
| `render_review_markdown(review_feedback, jokes?)` | Renders previously returned feedback as Markdown. |

**Resources**: `criticat://format-categories`, `criticat://schema/format-review` (JSON schema of the feedback), `criticat://reports/latest` (the last `reports/criticat_feedback.json`).

**Prompts**: `review_latex_pdf(pdf_path, focus?)` walks the model through validate, review and summarize.

### Development

```bash
sudo apt-get install poppler-utils  # needed for the PDF rendering tests
uv sync --all-groups
uv run pytest
uvx ruff check . && uvx ruff format --check .
```

The test suite never calls Vertex AI: the review chains are replaced with fakes, and real PDFs are generated on the fly. Tests that need Poppler are skipped when it is not installed. The MCP tests talk to the servers over in-memory, stdio subprocess and live SSE transports.

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