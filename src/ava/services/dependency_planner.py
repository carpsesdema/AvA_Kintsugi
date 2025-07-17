# src/ava/services/dependency_planner.py
from pathlib import Path
from typing import Dict, List, Any, Set
from dataclasses import dataclass
from src.ava.services.context_manager import GenerationContext


@dataclass
class FileGenerationSpec:
    """Specification for generating a single file with full context."""
    filename: str
    purpose: str
    dependencies: Set[str]
    dependents: Set[str]
    priority: int
    context: GenerationContext


class DependencyPlanner:
    """
    Plans the optimal order for generating files based on dependencies.

    Single Responsibility: Analyze dependencies and determine the optimal
    generation order to minimize integration issues.
    """

    def __init__(self, service_manager):
        self.service_manager = service_manager

    async def plan_generation_order(self, context: GenerationContext) -> List[FileGenerationSpec]:
        """Plan the optimal generation order based on dependencies."""
        files_to_generate = context.plan.get("files", [])

        # Build dependency graph from plan and living design context
        dependency_graph = self._build_dependency_graph(files_to_generate, context)

        # Perform topological sort to determine generation order
        generation_order = self._topological_sort(dependency_graph)

        # Update context with generation order
        context.dependency_order = generation_order

        # Build generation specifications
        specs = []
        for i, filename in enumerate(generation_order):
            file_info = next((f for f in files_to_generate if f["filename"] == filename), None)
            if not file_info:
                continue

            specs.append(FileGenerationSpec(
                filename=filename,
                purpose=file_info.get("purpose", ""),
                dependencies=dependency_graph.get(filename, {}).get("dependencies", set()),
                dependents=dependency_graph.get(filename, {}).get("dependents", set()),
                priority=i,
                context=context
            ))

        return specs

    def _build_dependency_graph(self, files_to_generate: List[Dict],
                                context: GenerationContext) -> Dict[str, Dict[str, Set[str]]]:
        """Build dependency graph from file purposes and existing context."""
        graph = {}
        file_purposes = {f["filename"]: f.get("purpose", "") for f in files_to_generate}

        for file_info in files_to_generate:
            filename = file_info["filename"]
            purpose = file_info.get("purpose", "")

            dependencies = set()
            dependents = set()

            # Analyze purpose text for dependency clues
            dependencies.update(self._extract_dependencies_from_purpose(purpose, file_purposes))

            # Use living design context for additional dependency info
            if context.living_design_context:
                living_deps = self._extract_dependencies_from_living_context(
                    filename, context.living_design_context
                )
                dependencies.update(living_deps)

            graph[filename] = {
                "dependencies": dependencies,
                "dependents": dependents
            }

        # Calculate dependents (reverse dependencies)
        for filename, data in graph.items():
            for dep in data["dependencies"]:
                if dep in graph:
                    graph[dep]["dependents"].add(filename)

        return graph

    def _extract_dependencies_from_purpose(self, purpose: str,
                                           file_purposes: Dict[str, str]) -> Set[str]:
        """Extract dependencies by analyzing purpose text."""
        dependencies = set()
        purpose_lower = purpose.lower()

        # Look for mentions of other files in the purpose
        for filename, other_purpose in file_purposes.items():
            file_stem = Path(filename).stem
            if file_stem.lower() in purpose_lower and filename != filename:
                dependencies.add(filename)

        # Common dependency patterns
        if "main" in purpose_lower and "main.py" in file_purposes:
            if purpose != file_purposes["main.py"]:  # Don't self-depend
                dependencies.add("main.py")

        return dependencies

    def _extract_dependencies_from_living_context(self, filename: str,
                                                  living_context: Dict[str, Any]) -> Set[str]:
        """Extract dependencies from living design context."""
        dependencies = set()

        # Use dependency graph from living design agent if available
        if "dependency_graph" in living_context:
            deps = living_context["dependency_graph"].get(filename, [])
            dependencies.update(deps)

        return dependencies

    def _topological_sort(self, graph: Dict[str, Dict[str, Set[str]]]) -> List[str]:
        """Perform topological sort to determine generation order."""
        # Kahn's algorithm for topological sorting
        in_degree = {node: 0 for node in graph}

        # Calculate in-degrees
        for node, data in graph.items():
            for dep in data["dependencies"]:
                if dep in in_degree:
                    in_degree[node] += 1

        # Queue nodes with no incoming edges
        queue = [node for node, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            node = queue.pop(0)
            result.append(node)

            # Remove this node and update in-degrees
            for dependent in graph[node]["dependents"]:
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        # Handle cycles by adding remaining nodes
        if len(result) < len(graph):
            remaining_nodes = sorted([node for node in graph if node not in result])
            result.extend(remaining_nodes)


        return result