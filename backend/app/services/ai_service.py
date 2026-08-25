
class AIService:
    @staticmethod
    async def score_lead(lead_data: dict) -> dict:
        # Mock AI Lead Scoring using OpenAI / Claude logic
        return {
            "score": 88.5,
            "reasoning": "High engagement, matching industry target, positive email sentiment."
        }

    @staticmethod
    async def generate_email(prompt: str, context: dict = None) -> dict:
        return {
            "subject": f"Follow up: {prompt[:30]}...",
            "body": f"Dear Customer,\n\nBased on our conversation regarding {prompt}, I would like to schedule a quick demo.\n\nBest regards,\nSales Team"
        }

    @staticmethod
    async def summarize_meeting(transcript: str) -> dict:
        return {
            "summary": "Discussed Q3 sales targets and product feature request for custom CRM dashboards.",
            "action_items": ["Send updated quote by Friday", "Schedule follow-up call next week"]
        }

ai_service = AIService()
