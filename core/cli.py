import asyncio

from core.agent import NexusAgent
from memory.store import get_recent_messages


async def chat():

    agent = NexusAgent()

    print("\n" + "=" * 55)
    print("                       NEXUS AI")
    print("                Your Personal AI Agent")
    print("=" * 55)

    print("\nCOMMANDS")
    print("  /help       - Show commands")
    print("  /skills     - List available skills")
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
                print("/exit\n")
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