from app.config import settings
from langchain_groq import ChatGroq

print("Provider:", settings.llm_provider)
print("Model:", settings.model_name)

llm = ChatGroq(
    model=settings.model_name,
    api_key=settings.groq_api_key
)

response = llm.invoke("Say hello to AURA in one short sentence.")

print("\nGroq response:")
print(response.content)