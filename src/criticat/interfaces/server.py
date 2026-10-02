"""
Model Context Protocol (MCP) server for Criticat.

Exposes PDF review tools, reference resources and a guided review prompt over
stdio (default) or SSE. stdout is reserved for the MCP protocol when running
over stdio, so all logging goes to stderr.
"""

import argparse
import json
import logging
import os
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal, get_args

import anyio
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ResourceError, ToolError
from pdf2image import pdfinfo_from_path
from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError

from criticat.models.config.app import JokeMode
from criticat.models.formatting import FormatCategoryName, FormatReview
from criticat.models.states.review import ReviewState
from criticat.reporting import render_review_markdown, summarize_review
from criticat.use_cases.service import ReviewError, ReviewService, validate_pdf_path

logger = logging.getLogger(__name__)

SERVER_NAME = "Criticat"
SERVER_INSTRUCTIONS = (
    "Criticat reviews rendered PDF documents (typically LaTeX output) for visual "
    "formatting problems such as spacing, alignment, occlusion and font quality "
    "using Gemini on Vertex AI. Call `validate_pdf` first to cheaply check a "
    "file, `check_configuration` to diagnose setup issues, then `review_pdf` to "
    "run the review. Reviews can take a while and incur Vertex AI usage."
)
DEFAULT_REPORTS_DIR = Path("reports")
REPORT_FILENAME = "criticat_feedback.json"

JokeModeName = Literal["none", "default", "chaotic"]
Transport = Literal["stdio", "sse"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _review_payload(review: ReviewState, include_markdown: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "summary": summarize_review(review).model_dump(),
        "review_feedback": {
            provider: feedback.model_dump()
            for provider, feedback in review.review_feedback.items()
        },
        "jokes": list(review.jokes),
    }
    if include_markdown:
        payload["markdown"] = render_review_markdown(review)
    return payload


def build_server(
    service: ReviewService | None = None,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    **settings: Any,
) -> FastMCP:
    """Create a configured Criticat MCP server."""
    review_service = service or ReviewService()
    server = FastMCP(name=SERVER_NAME, instructions=SERVER_INSTRUCTIONS, **settings)

    @server.tool(
        name="review_pdf",
        description=(
            "Review a PDF for visual formatting issues with Gemini on Vertex AI. "
            "Returns a summary (issue counts, blocking flag), per-provider "
            "structured feedback, cat jokes and a Markdown report."
        ),
    )
    async def review_pdf(
        pdf_path: str,
        ctx: Context,
        project_id: str | None = None,
        location: str | None = None,
        joke_mode: JokeModeName = "default",
        include_markdown: bool = True,
    ) -> dict[str, Any]:
        try:
            prepared = review_service.prepare(
                pdf_path=pdf_path,
                project_id=project_id,
                location=location,
                joke_mode=joke_mode,
            )
        except ReviewError as e:
            raise ToolError(str(e)) from e

        await ctx.info(f"Reviewing {prepared.config.pdf_path}")
        await ctx.report_progress(0, 1)
        try:
            review = await anyio.to_thread.run_sync(review_service.execute, prepared)
        except ReviewError as e:
            raise ToolError(str(e)) from e
        await ctx.report_progress(1, 1)

        payload = _review_payload(review, include_markdown=include_markdown)
        payload["request"] = {
            "pdf_path": prepared.config.pdf_path,
            "project_id": prepared.provider_config.project_id,
            "location": prepared.provider_config.location,
            "joke_mode": prepared.config.joke_mode.value,
        }
        return payload

    @server.tool(
        name="validate_pdf",
        description=(
            "Check that a path points to a readable PDF and report its size and "
            "page count. Does not call Vertex AI."
        ),
    )
    def validate_pdf(pdf_path: str) -> dict[str, Any]:
        try:
            path = validate_pdf_path(pdf_path)
        except ReviewError as e:
            raise ToolError(str(e)) from e

        page_count: int | None = None
        warning: str | None = None
        try:
            page_count = int(pdfinfo_from_path(str(path))["Pages"])
        except PDFInfoNotInstalledError:
            warning = "Poppler is not installed; page count unavailable."
        except (PDFPageCountError, KeyError, ValueError) as e:
            raise ToolError(f"PDF could not be parsed: {path} ({e})") from e

        result: dict[str, Any] = {
            "valid": True,
            "pdf_path": str(path),
            "size_bytes": path.stat().st_size,
            "page_count": page_count,
        }
        if warning:
            result["warning"] = warning
        return result

    @server.tool(
        name="check_configuration",
        description=(
            "Report the resolved GCP project/location, Poppler availability and "
            "supported joke modes so setup problems can be diagnosed."
        ),
    )
    def check_configuration() -> dict[str, Any]:
        problems: list[str] = []
        try:
            project_id: str | None = review_service.resolve_project_id()
        except ReviewError as e:
            project_id = None
            problems.append(str(e))

        poppler = shutil.which("pdftoppm") is not None
        if not poppler:
            problems.append(
                "Poppler (pdftoppm) not found on PATH; PDF rendering will fail."
            )

        return {
            "ready": not problems,
            "project_id": project_id,
            "location": review_service.resolve_location(),
            "poppler_available": poppler,
            "joke_modes": [mode.value for mode in JokeMode],
            "problems": problems,
        }

    @server.tool(
        name="render_review_markdown",
        description=(
            "Render a Markdown report (e.g. for a PR comment) from review_feedback "
            "and jokes as returned by review_pdf or stored in the latest report."
        ),
    )
    def render_markdown(
        review_feedback: dict[str, FormatReview],
        jokes: list[str] | None = None,
    ) -> str:
        return render_review_markdown(
            ReviewState(review_feedback=review_feedback, jokes=jokes or [])
        )

    @server.resource(
        "criticat://format-categories",
        name="format-categories",
        description="Formatting issue categories Criticat can report.",
        mime_type="application/json",
    )
    def format_categories() -> str:
        return json.dumps(list(get_args(FormatCategoryName)))

    @server.resource(
        "criticat://schema/format-review",
        name="format-review-schema",
        description="JSON schema of the structured feedback produced per provider.",
        mime_type="application/json",
    )
    def format_review_schema() -> str:
        return json.dumps(FormatReview.model_json_schema())

    @server.resource(
        "criticat://reports/latest",
        name="latest-report",
        description="The most recent review written to reports/criticat_feedback.json.",
        mime_type="application/json",
    )
    def latest_report() -> str:
        report = reports_dir / REPORT_FILENAME
        if not report.is_file():
            raise ResourceError(f"No review report found at {report.resolve()}")
        content = report.read_text(encoding="utf-8")
        ReviewState.model_validate_json(content)
        return content

    @server.prompt(
        name="review_latex_pdf",
        description="Guided workflow to review a compiled LaTeX PDF and propose fixes.",
    )
    def review_latex_pdf(pdf_path: str, focus: str = "") -> str:
        focus_line = f"Pay special attention to: {focus}.\n" if focus.strip() else ""
        return (
            f"Review the compiled LaTeX document at `{pdf_path}` with Criticat.\n"
            f"{focus_line}"
            "1. Call `validate_pdf` to confirm the file is a readable PDF.\n"
            "2. Call `review_pdf` with the same path.\n"
            "3. Summarize blocking issues (critical/error) first, then warnings.\n"
            "4. For each issue, propose a concrete LaTeX change (package, command "
            "or length) that would fix the likely cause.\n"
        )

    return server


mcp = build_server()


def configure_logging(level: str = "INFO") -> None:
    """Route application logs to stderr so stdio transport stays clean."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "stream", None) is sys.stdout:
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(level)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="criticat-mcp", description="Run the Criticat MCP server."
    )
    parser.add_argument(
        "--transport",
        choices=get_args(Transport),
        default=os.environ.get("CRITICAT_MCP_TRANSPORT", "stdio"),
        help="MCP transport (default: stdio, env: CRITICAT_MCP_TRANSPORT)",
    )
    parser.add_argument("--host", default=None, help="Bind host for SSE transport")
    parser.add_argument(
        "--port", type=int, default=None, help="Bind port for SSE transport"
    )
    parser.add_argument(
        "--log-level",
        choices=get_args(LogLevel),
        default=os.environ.get("CRITICAT_LOG_LEVEL", "INFO").upper(),
        help="Log level (env: CRITICAT_LOG_LEVEL)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point for the ``criticat-mcp`` command."""
    args = parse_args(argv)
    configure_logging(args.log_level)
    if args.host is not None:
        mcp.settings.host = args.host
    if args.port is not None:
        mcp.settings.port = args.port

    logger.info("Starting Criticat MCP server (%s transport)", args.transport)
    try:
        mcp.run(transport=args.transport)
    except KeyboardInterrupt:
        logger.info("Criticat MCP server interrupted")


if __name__ == "__main__":
    main()
