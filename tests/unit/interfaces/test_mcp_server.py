"""Protocol-level tests for the Criticat FastMCP server (in-memory transport)."""

import json
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

import pytest
from mcp import types
from mcp.client.session import ClientSession
from mcp.server.fastmcp import FastMCP
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session

from criticat.interfaces import server as server_module
from criticat.interfaces.server import build_server
from criticat.models.config.app import JokeMode
from criticat.models.formatting import FormatReview
from criticat.models.models import VertexAIConfig
from criticat.use_cases.service import ReviewService
from tests.conftest import requires_poppler
from tests.factories import (
    CATEGORY_NAMES,
    FakeReviewPDFFactory,
    make_feedback,
    make_issue,
    make_review_state,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def factory() -> FakeReviewPDFFactory:
    return FakeReviewPDFFactory(
        result={
            "review": make_review_state(
                feedback=make_feedback(
                    ("text_occlusion", make_issue("critical", "Figure covers text")),
                    ("line_spacing", make_issue("warning")),
                ),
                jokes=["Hiss."],
            )
        }
    )


@pytest.fixture
def project_id() -> dict[str, str | None]:
    return {"value": "env-project"}


@pytest.fixture
def reports_dir(tmp_path: Path) -> Path:
    return tmp_path / "reports"


@pytest.fixture
def mcp_server(
    factory: FakeReviewPDFFactory,
    project_id: dict[str, str | None],
    reports_dir: Path,
) -> FastMCP:
    service = ReviewService(
        review_pdf_factory=factory,
        project_id_resolver=lambda: project_id["value"],
        location_resolver=lambda: "europe-west1",
    )
    return build_server(service=service, reports_dir=reports_dir)


def connected(server: FastMCP) -> AbstractAsyncContextManager[ClientSession]:
    return create_connected_server_and_client_session(server._mcp_server)


def text_of(result: types.CallToolResult) -> str:
    assert len(result.content) == 1
    content = result.content[0]
    assert isinstance(content, types.TextContent)
    return content.text


def json_of(result: types.CallToolResult) -> Any:
    assert not result.isError, text_of(result)
    return json.loads(text_of(result))


class TestDiscovery:
    async def test_server_identity(self, mcp_server: FastMCP) -> None:
        assert mcp_server.name == "Criticat"
        assert "review_pdf" in (mcp_server.instructions or "")

    async def test_lists_tools(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert set(tools) == {
                "review_pdf",
                "validate_pdf",
                "check_configuration",
                "render_review_markdown",
            }
            assert all(tool.description for tool in tools.values())

    async def test_review_pdf_schema(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            schema = tools["review_pdf"].inputSchema
            assert schema["required"] == ["pdf_path"]
            assert set(schema["properties"]) == {
                "pdf_path",
                "project_id",
                "location",
                "joke_mode",
                "include_markdown",
            }
            assert schema["properties"]["joke_mode"]["enum"] == [
                mode.value for mode in JokeMode
            ]
            assert schema["properties"]["joke_mode"]["default"] == "default"

    async def test_context_is_not_exposed_in_schema(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert "ctx" not in tools["review_pdf"].inputSchema["properties"]

    async def test_lists_resources(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            uris = {str(r.uri) for r in (await session.list_resources()).resources}
            assert uris == {
                "criticat://format-categories",
                "criticat://schema/format-review",
                "criticat://reports/latest",
            }

    async def test_lists_prompts(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            prompts = (await session.list_prompts()).prompts
            assert [p.name for p in prompts] == ["review_latex_pdf"]
            args = {a.name: a.required for a in prompts[0].arguments or []}
            assert args == {"pdf_path": True, "focus": False}


class TestReviewPdfTool:
    async def test_returns_structured_review(
        self,
        mcp_server: FastMCP,
        factory: FakeReviewPDFFactory,
        fake_pdf: Path,
    ) -> None:
        async with connected(mcp_server) as session:
            payload = json_of(
                await session.call_tool(
                    "review_pdf",
                    {"pdf_path": str(fake_pdf), "joke_mode": "chaotic"},
                )
            )

            assert payload["request"] == {
                "pdf_path": str(fake_pdf.resolve()),
                "project_id": "env-project",
                "location": "europe-west1",
                "joke_mode": "chaotic",
            }
            assert payload["summary"] == {
                "issue_count": 2,
                "issues_by_status": {
                    "critical": 1,
                    "error": 0,
                    "warning": 1,
                    "info": 0,
                },
                "has_blocking_issues": True,
                "providers": ["vertex_ai"],
            }
            assert payload["jokes"] == ["Hiss."]
            FormatReview.model_validate(payload["review_feedback"]["vertex_ai"])
            assert "Figure covers text" in payload["markdown"]
            assert "document_images" not in json.dumps(payload)
            assert factory.run_configs == [
                {"pdf_path": str(fake_pdf.resolve()), "joke_mode": JokeMode.CHAOTIC}
            ]

    async def test_explicit_project_and_location(
        self,
        mcp_server: FastMCP,
        factory: FakeReviewPDFFactory,
        fake_pdf: Path,
    ) -> None:
        async with connected(mcp_server) as session:
            json_of(
                await session.call_tool(
                    "review_pdf",
                    {
                        "pdf_path": str(fake_pdf),
                        "project_id": "explicit",
                        "location": "asia-east1",
                    },
                )
            )
            assert factory.provider_configs == [
                [VertexAIConfig(project_id="explicit", location="asia-east1")]
            ]

    async def test_markdown_can_be_omitted(
        self, mcp_server: FastMCP, fake_pdf: Path
    ) -> None:
        async with connected(mcp_server) as session:
            payload = json_of(
                await session.call_tool(
                    "review_pdf",
                    {"pdf_path": str(fake_pdf), "include_markdown": False},
                )
            )
            assert "markdown" not in payload

    async def test_missing_project_is_tool_error(
        self,
        mcp_server: FastMCP,
        factory: FakeReviewPDFFactory,
        project_id: dict[str, str | None],
        fake_pdf: Path,
    ) -> None:
        async with connected(mcp_server) as session:
            project_id["value"] = None
            result = await session.call_tool("review_pdf", {"pdf_path": str(fake_pdf)})
            assert result.isError
            assert "No GCP project ID provided" in text_of(result)
            assert factory.provider_configs == []

    async def test_missing_file_is_tool_error(
        self, mcp_server: FastMCP, tmp_path: Path
    ) -> None:
        async with connected(mcp_server) as session:
            result = await session.call_tool(
                "review_pdf", {"pdf_path": str(tmp_path / "missing.pdf")}
            )
            assert result.isError
            assert "PDF file not found" in text_of(result)

    async def test_invalid_joke_mode_is_rejected(
        self, mcp_server: FastMCP, fake_pdf: Path
    ) -> None:
        async with connected(mcp_server) as session:
            result = await session.call_tool(
                "review_pdf", {"pdf_path": str(fake_pdf), "joke_mode": "loud"}
            )
            assert result.isError
            assert "joke_mode" in text_of(result)

    async def test_missing_required_argument(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            result = await session.call_tool("review_pdf", {})
            assert result.isError
            assert "pdf_path" in text_of(result)

    async def test_pipeline_failure_is_tool_error(
        self,
        mcp_server: FastMCP,
        factory: FakeReviewPDFFactory,
        fake_pdf: Path,
    ) -> None:
        async with connected(mcp_server) as session:
            factory.error = RuntimeError("Vertex AI quota exceeded")
            result = await session.call_tool("review_pdf", {"pdf_path": str(fake_pdf)})
            assert result.isError
            assert "Vertex AI quota exceeded" in text_of(result)

    async def test_server_survives_errors(
        self,
        mcp_server: FastMCP,
        factory: FakeReviewPDFFactory,
        fake_pdf: Path,
    ) -> None:
        async with connected(mcp_server) as session:
            factory.error = RuntimeError("transient")
            assert (
                await session.call_tool("review_pdf", {"pdf_path": str(fake_pdf)})
            ).isError
            factory.error = None
            json_of(await session.call_tool("review_pdf", {"pdf_path": str(fake_pdf)}))

    async def test_reports_progress_and_logs(
        self, mcp_server: FastMCP, fake_pdf: Path
    ) -> None:
        progress: list[types.ProgressNotificationParams] = []
        logs: list[types.LoggingMessageNotificationParams] = []

        async def on_message(message: object) -> None:
            if isinstance(message, types.ServerNotification) and isinstance(
                message.root, types.ProgressNotification
            ):
                progress.append(message.root.params)

        async def on_log(params: types.LoggingMessageNotificationParams) -> None:
            logs.append(params)

        async with create_connected_server_and_client_session(
            mcp_server._mcp_server,
            message_handler=on_message,
            logging_callback=on_log,
        ) as client:
            params = types.CallToolRequestParams.model_validate(
                {
                    "name": "review_pdf",
                    "arguments": {"pdf_path": str(fake_pdf)},
                    "_meta": {"progressToken": "review-1"},
                }
            )
            result = await client.send_request(
                types.ClientRequest(
                    types.CallToolRequest(method="tools/call", params=params)
                ),
                types.CallToolResult,
            )

        assert not result.isError
        assert [(p.progressToken, p.progress, p.total) for p in progress] == [
            ("review-1", 0, 1),
            ("review-1", 1, 1),
        ]
        assert any("Reviewing" in str(log.data) for log in logs)


class TestValidatePdfTool:
    @requires_poppler
    async def test_reports_page_count(
        self, mcp_server: FastMCP, sample_pdf: Path
    ) -> None:
        async with connected(mcp_server) as session:
            payload = json_of(
                await session.call_tool("validate_pdf", {"pdf_path": str(sample_pdf)})
            )
            assert payload == {
                "valid": True,
                "pdf_path": str(sample_pdf.resolve()),
                "size_bytes": sample_pdf.stat().st_size,
                "page_count": 2,
            }

    @requires_poppler
    async def test_corrupt_pdf_is_tool_error(
        self, mcp_server: FastMCP, fake_pdf: Path
    ) -> None:
        async with connected(mcp_server) as session:
            result = await session.call_tool(
                "validate_pdf", {"pdf_path": str(fake_pdf)}
            )
            assert result.isError
            assert "could not be parsed" in text_of(result)

    async def test_without_poppler_warns(
        self,
        mcp_server: FastMCP,
        fake_pdf: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async with connected(mcp_server) as session:

            def missing(path: str) -> dict[str, Any]:
                raise server_module.PDFInfoNotInstalledError("no poppler")

            monkeypatch.setattr(server_module, "pdfinfo_from_path", missing)
            payload = json_of(
                await session.call_tool("validate_pdf", {"pdf_path": str(fake_pdf)})
            )
            assert payload["valid"] is True
            assert payload["page_count"] is None
            assert "Poppler" in payload["warning"]

    async def test_invalid_path_is_tool_error(
        self, mcp_server: FastMCP, tmp_path: Path
    ) -> None:
        async with connected(mcp_server) as session:
            path = tmp_path / "notes.txt"
            path.write_text("hi")
            result = await session.call_tool("validate_pdf", {"pdf_path": str(path)})
            assert result.isError
            assert "Expected a .pdf file" in text_of(result)


class TestCheckConfigurationTool:
    async def test_ready(
        self, mcp_server: FastMCP, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async with connected(mcp_server) as session:
            monkeypatch.setattr(server_module.shutil, "which", lambda name: "/bin/x")
            payload = json_of(await session.call_tool("check_configuration", {}))
            assert payload == {
                "ready": True,
                "project_id": "env-project",
                "location": "europe-west1",
                "poppler_available": True,
                "joke_modes": ["none", "default", "chaotic"],
                "problems": [],
            }

    async def test_reports_problems(
        self,
        mcp_server: FastMCP,
        project_id: dict[str, str | None],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async with connected(mcp_server) as session:
            project_id["value"] = None
            monkeypatch.setattr(server_module.shutil, "which", lambda name: None)
            payload = json_of(await session.call_tool("check_configuration", {}))
            assert payload["ready"] is False
            assert payload["project_id"] is None
            assert payload["poppler_available"] is False
            assert len(payload["problems"]) == 2


class TestRenderMarkdownTool:
    async def test_renders_feedback(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            feedback = make_feedback(("font_quality", make_issue("error", "Blurry")))
            result = await session.call_tool(
                "render_review_markdown",
                {
                    "review_feedback": {"vertex_ai": feedback.model_dump()},
                    "jokes": ["Meow."],
                },
            )
            markdown = text_of(result)
            assert not result.isError
            assert "`font_quality`: Blurry" in markdown
            assert "> Meow." in markdown

    async def test_rejects_invalid_feedback(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            result = await session.call_tool(
                "render_review_markdown",
                {"review_feedback": {"vertex_ai": {"categories": "nope"}}},
            )
            assert result.isError


class TestResources:
    async def read(self, session: ClientSession, uri: str) -> str:
        result = await session.read_resource(uri)  # type: ignore[arg-type]
        content = result.contents[0]
        assert isinstance(content, types.TextResourceContents)
        assert content.mimeType == "application/json"
        return content.text

    async def test_format_categories(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            text = await self.read(session, "criticat://format-categories")
            assert tuple(json.loads(text)) == CATEGORY_NAMES

    async def test_format_review_schema(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            schema = json.loads(
                await self.read(session, "criticat://schema/format-review")
            )
            assert schema == FormatReview.model_json_schema()

    async def test_latest_report(self, mcp_server: FastMCP, reports_dir: Path) -> None:
        async with connected(mcp_server) as session:
            reports_dir.mkdir()
            report = make_review_state().model_dump_json(exclude={"document_images"})
            (reports_dir / "criticat_feedback.json").write_text(report)
            assert await self.read(session, "criticat://reports/latest") == report

    async def test_latest_report_missing(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            with pytest.raises(McpError, match="No review report found"):
                await session.read_resource("criticat://reports/latest")  # type: ignore[arg-type]

    async def test_latest_report_corrupt(
        self, mcp_server: FastMCP, reports_dir: Path
    ) -> None:
        async with connected(mcp_server) as session:
            reports_dir.mkdir()
            (reports_dir / "criticat_feedback.json").write_text("{not json")
            with pytest.raises(McpError):
                await session.read_resource("criticat://reports/latest")  # type: ignore[arg-type]

    async def test_unknown_resource(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            with pytest.raises(McpError):
                await session.read_resource("criticat://nope")  # type: ignore[arg-type]


class TestPrompt:
    async def test_review_prompt_with_focus(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            result = await session.get_prompt(
                "review_latex_pdf", {"pdf_path": "thesis.pdf", "focus": "tables"}
            )
            message = result.messages[0]
            assert message.role == "user"
            assert isinstance(message.content, types.TextContent)
            text = message.content.text
            assert "`thesis.pdf`" in text
            assert "Pay special attention to: tables." in text
            assert text.index("validate_pdf") < text.index("review_pdf`")

    async def test_review_prompt_without_focus(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            result = await session.get_prompt("review_latex_pdf", {"pdf_path": "a.pdf"})
            assert isinstance(result.messages[0].content, types.TextContent)
            assert "special attention" not in result.messages[0].content.text

    async def test_prompt_requires_pdf_path(self, mcp_server: FastMCP) -> None:
        async with connected(mcp_server) as session:
            with pytest.raises(McpError):
                await session.get_prompt("review_latex_pdf", {})


async def test_unknown_tool(mcp_server: FastMCP) -> None:
    async with connected(mcp_server) as session:
        result = await session.call_tool("does_not_exist", {})
        assert result.isError
        assert "Unknown tool" in text_of(result)


async def test_default_server_uses_real_service() -> None:
    tools = {tool.name for tool in await server_module.mcp.list_tools()}
    assert "review_pdf" in tools
