import json
import re
from agents.base_agent import Agent

class ImplementationAgent(Agent):
    def __init__(self, name, client, prompt="", gen_kwargs=None):
        super().__init__(name, client, prompt, gen_kwargs)
        self.prompt = """
You are an Implementation Agent responsible for executing the milestones outlined in the plan.md file. Your task is to implement or update ONE milestone at a time, focusing on creating or modifying the index.html and style.css files in the artifacts folder.

Instructions:
1. Read the plan.md file to identify the current milestone to work on.
2. Implement or update the appropriate milestone in index.html and style.css.
3. Mark the completed milestone as done in plan.md by changing "[ ]" to "[x]".
4. Provide a brief summary of the changes made.

Remember to:
- Focus on one milestone at a time.
- Write clean, semantic HTML and CSS.
- Ensure your implementation aligns with the design described in the plan.
- Be mindful of responsive design principles.
- Use appropriate HTML5 tags and CSS3 features.

If given feedback to fix a milestone:
1. Carefully review the feedback.
2. Make the necessary adjustments to index.html and/or style.css.
3. Provide a summary of the changes made in response to the feedback.

Always strive for high-quality, maintainable code that accurately reflects the design specifications in the plan.
"""

    async def execute(self, message_history):
        # First, let's get the current state of plan.md
        plan_md = self._get_artifact_content('plan.md')
        
        # Identify the next uncompleted milestone
        next_milestone = self._get_next_milestone(plan_md)
        
        if not next_milestone:
            return "All milestones have been completed. Please provide new instructions or feedback."

        # Add the specific milestone to work on to the message history
        message_history.append({
            "role": "system",
            "content": f"Focus on implementing this milestone: {next_milestone}"
        })

        # Execute the main logic from the parent class
        response = await super().execute(message_history)

        # Update plan.md to mark the milestone as completed
        updated_plan = self._mark_milestone_complete(plan_md, next_milestone)
        await self._update_artifact('plan.md', updated_plan)

        return response

    def _get_artifact_content(self, filename):
        artifacts = self._build_system_prompt().split('<ARTIFACTS>\n')[1].split('</ARTIFACTS>')[0]
        file_content = re.search(f"<FILE name='{filename}'>\n(.*?)\n</FILE>", artifacts, re.DOTALL)
        return file_content.group(1) if file_content else ""

    def _get_next_milestone(self, plan_md):
        milestones = re.findall(r'- \[ \] (.*)', plan_md)
        return milestones[0] if milestones else None

    def _mark_milestone_complete(self, plan_md, completed_milestone):
        return plan_md.replace(f"- [ ] {completed_milestone}", f"- [x] {completed_milestone}", 1)

    async def _update_artifact(self, filename, content):
        await self.client.chat.completions.create(
            messages=[{
                "role": "system",
                "content": "Update the artifact file."
            }],
            tools=[{
                "type": "function",
                "function": {
                    "name": "updateArtifact",
                    "description": "Update an artifact file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "contents": {"type": "string"}
                        },
                        "required": ["filename", "contents"]
                    }
                }
            }],
            tool_choice={"type": "function", "function": {"name": "updateArtifact"}},
            **self.gen_kwargs
        )

def callAgent(agent_type):
    if agent_type == 'implementation':
        return ImplementationAgent(name="Implementation Agent", client=client)
    # Add other agent types here if needed
    return None
