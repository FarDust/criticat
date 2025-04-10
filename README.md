# 😼 Criticat

A GitHub Action for automated PDF document review using Gemini AI.

## Overview

Criticat reviews PDF documents for formatting issues and provides feedback as GitHub PR comments. It uses Google's Gemini 1.5 Flash model to analyze document layout and structure visually.

## Features

- 🔍 **Visual PDF Analysis**: Converts PDFs to images for layout analysis
- 🤖 **AI-Powered Reviews**: Uses Gemini 1.5 Flash to evaluate document formatting
- 💬 **PR Comments**: Automatically comments on PRs with detailed feedback
- 😺 **Customizable Jokes**: Adds sarcastic cat-themed jokes based on configuration

## Requirements

- Google Cloud project with Vertex AI API enabled
- GitHub repository with workflow permissions
- PDF documents to analyze

## Usage

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

Criticat is built using:
- LangChain + LangGraph for workflow orchestration
- Pydantic for configuration and state validation
- Typer for CLI interface
- Vertex AI for LLM integration

## License

MIT