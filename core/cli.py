import asyncio

from core.agent import NexusAgent
from memory.store import get_recent_messages
from core.settings import load_settings


async def chat():

    agent = NexusAgent()

    print("\n" + "=" * 55)
    print("                       NEXUS AI")
    print("                Your Personal AI Agent")
    print("=" * 55)

    print("\nCOMMANDS")
    print("  /help       - Show commands")
    print("  /skills     - List available skills")    
    print("  /tools      - List available tools")
    print("  /agents     - List specialist agents")
    print("  /use        - Use a specialist agent")
    print("  /history    - View conversation history")
    print("  /exit       - Exit NEXUS AI")

    print("\nNEXUS AI CONTROL CENTRE READY.\n")

    while True:

        try:
            question = input("YOU: ").strip()

            if not question:
                continue

            command = question.lower()

            if command == "/exit":
                print("\nNEXUS AI: Goodbye!")
                break

            elif command == "/help":
                print("\nCOMMANDS")
                print("/skills")
                print("/agents")
                print("/use <skill> <your request>")
                print("/history")
                print("/tools")
                print("/config")
                print("/research <url>")
                print("/exit\n")
                continue
            
            elif command == "/tools":
                print("\nAVAILABLE TOOLS")
                print("----------------")
                for tool in agent.available_tools():
                    print("-", tool)
                print()
                continue   
         
            elif command == "/config":
                settings = load_settings()

                print("\nNEXUS AI CONFIGURATION")
                print("----------------------")
                print("Version:", settings["version"])
                print("AI Provider:", settings["ai_provider"])
                print("Model:", settings["model"] or "Not configured")
                print("Memory:", settings["memory_enabled"])
                print("Autonomous Mode:", settings["autonomous_mode"])
                print("Approval Required:", settings["require_approval"])
                print("File Deletion:", settings["allow_file_deletion"])
                print("Registered Skills:", len(settings["enabled_skills"]))
                print("Registered Agents:", len(settings["agents"]))
                print()
                continue           
           
            elif command.startswith("/research"):
                parts = question.split(maxsplit=1)

                if len(parts) < 2:
                    print("\nUsage: /research https://example.com\n")
                    continue

                url = parts[1].strip()

                print("\nNEXUS AI: Requesting permission to research webpage...\n")

                result = await agent.use_tool("web_research", url=url)

                print("\nRESEARCH RESULT")
                print("----------------")

                if isinstance(result, dict):
                    print("Title:", result.get("title", "Unknown"))
                    print("URL:", result.get("url", "Unknown"))
                    print("\nCONTENT:")
                    print(result.get("content", "No content"))
                    print("\nStatus:", result.get("status", "Unknown"))
                else:
                    print(result)
                continue

            elif command == "/skills":
                print("\nAVAILABLE SKILLS")
                print("----------------")
                for skill in agent.available_skills():
                    print("-", skill)
                print()
                continue

            elif command == "/agents":
                from agents.manager import list_agents

                print("\nREGISTERED SPECIALIST AGENTS")
                print("----------------------------")

                for agent_id, details in list_agents().items():
                    print(f"\n{details['name']}")
                    print("ID:", agent_id)
                    print("Skills:", ", ".join(details["skills"]))

                print()
                continue

            elif command.startswith("/use "):
                parts = question.split(maxsplit=2)

                if len(parts) < 3:
                    print(
                        "\nUsage: /use <skill_name> <your request>\n"
                    )
                    continue

                skill_name = parts[1].lower()
                specialist_question = parts[2]

                if skill_name not in agent.available_skills():
                    print("\nNEXUS AI: Unknown skill.\n")
                    continue

                print(
                    f"\nNEXUS AI: Sending request to "
                    f"{skill_name} specialist...\n"
                )

                answer = await agent.ask_specialist(
                    skill_name,
                    specialist_question
                )

                print(f"NEXUS AI: {answer}\n")
                continue

            elif command == "/history":
                history = get_recent_messages(10)

                print("\nCONVERSATION HISTORY")
                print("--------------------")

                for message in history:
                    print(
                        f"{message['role'].upper()}: "
                        f"{message['content']}"
                    )

                print()
                continue

            print("\nNEXUS AI: Thinking...\n")

            answer = await agent.ask(question)

            print(f"NEXUS AI: {answer}\n")

        except KeyboardInterrupt:
            print("\n\nNEXUS AI: Session interrupted.")
            break

        except Exception as error:
            print(f"\nNEXUS AI ERROR: {error}\n")


if __name__ == "__main__":
    asyncio.run(chat())