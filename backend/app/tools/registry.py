from app.tools.base import KnowledgeTool, ToolNotFoundError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, KnowledgeTool] = {}

    def register(self, tool: KnowledgeTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool is already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, tool_name: str) -> KnowledgeTool:
        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise ToolNotFoundError(tool_name) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))


def build_default_tool_registry() -> ToolRegistry:
    from app.tools.knowledge_extraction import KnowledgeExtractionTool
    from app.tools.page_relationship import PageRelationshipTool
    from app.tools.source_parse import SourceParseTool
    from app.tools.wiki_page_update import WikiPageUpdateTool

    registry = ToolRegistry()
    registry.register(SourceParseTool())
    registry.register(KnowledgeExtractionTool())
    registry.register(WikiPageUpdateTool())
    registry.register(PageRelationshipTool())
    return registry
