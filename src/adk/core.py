from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


ToolHandler = Callable[..., Any]
SkillHandler = Callable[..., str]


@dataclass
class Tool:
    name: str
    description: str
    handler: ToolHandler


@dataclass
class Skill:
    name: str
    description: str
    handler: SkillHandler


@dataclass
class AgentSpec:
    name: str
    role: str
    tool_names: list[str] = field(default_factory=list)
    skill_names: list[str] = field(default_factory=list)


class ADKRuntime:
    def __init__(self) -> None:
        self.tools: dict[str, Tool] = {}
        self.skills: dict[str, Skill] = {}
        self.agents: dict[str, AgentSpec] = {}

    def register_tool(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def register_skill(self, skill: Skill) -> None:
        self.skills[skill.name] = skill

    def register_agent(self, agent: AgentSpec) -> None:
        self.agents[agent.name] = agent

    def list_agents(self) -> list[dict[str, Any]]:
        return [
            {
                "name": agent.name,
                "role": agent.role,
                "tools": agent.tool_names,
                "skills": agent.skill_names,
            }
            for agent in self.agents.values()
        ]

    def run_tool(self, agent_name: str, tool_name: str, **kwargs: Any) -> Any:
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_name}")
        if tool_name not in agent.tool_names:
            raise ValueError(f"Tool {tool_name} is not enabled for agent {agent_name}")

        tool = self.tools.get(tool_name)
        if not tool:
            raise ValueError(f"Unknown tool: {tool_name}")
        return tool.handler(**kwargs)

    def run_skill(self, agent_name: str, skill_name: str, **kwargs: Any) -> str:
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"Unknown agent: {agent_name}")
        if skill_name not in agent.skill_names:
            raise ValueError(f"Skill {skill_name} is not enabled for agent {agent_name}")

        skill = self.skills.get(skill_name)
        if not skill:
            raise ValueError(f"Unknown skill: {skill_name}")
        return skill.handler(**kwargs)
