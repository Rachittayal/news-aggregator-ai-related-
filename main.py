from app.runner import run_scrapers


def main(hours: int=25000) -> dict:
    results= run_scrapers(hours=hours)
    
    print(f"Scraped {len(results['youtube'])} YouTube videos, "
          f"{len(results['openai'])} OpenAI articles, "
          f"{len(results['anthropic'])} Anthropic articles")    
    
    return results
if __name__ == "__main__":
    main(hours=250000)    
