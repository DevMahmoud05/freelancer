from flask import Flask, jsonify
import asyncio
import os
import pickle
import textwrap
from dotenv import load_dotenv
import requests
import telegram
from bs4 import BeautifulSoup
from keep_alive import keep_alive

keep_alive()
load_dotenv()

bot_token = os.getenv('BOT_TOKEN')
print("bot_token:", bot_token)

app = Flask(__name__)
bot = telegram.Bot(token=bot_token)

# Function to load previously sent jobs
sent_jobs = set()


def load_sent_jobs():
    if os.path.exists("sent_jobs.pkl"):
        with open("sent_jobs.pkl", "rb") as f:
            return pickle.load(f)
    return set()


sent_jobs = load_sent_jobs()


# Function to save sent jobs
def save_sent_jobs(sent_jobs):
    with open("sent_jobs.pkl", "wb") as f:
        pickle.dump(sent_jobs, f)


def generate_message(job):
    original_description = job.get('desc', 'No description available')
    truncated_description = textwrap.shorten(original_description, width=500)

    output = "🔐 Verification" if job.get('payment', False) else ""
    output2 = "💰 Made a Deposit" if job.get('deposit',
                                            False) else "⭕ Without Deposit"
    msg_link = f'https://www.freelancer.com{job.get("bid", "")}'

    msg = (f"💡 {job.get('title', 'No title')}\n\n"
           f"{output}\n\n{output2}\n\n"
           f"💵 Price: {job.get('price', 'No price')}\n\n"
           f"💼 Bids: {job.get('bidNum', 'No bidNum')}\n\n"
           f"🕰️Time{job.get('time', ' ')}\n"
           f"🎨 Description\n{truncated_description}\n\n{msg_link}")

    return msg


async def scrape_and_send_jobs():
    url = "https://www.freelancer.com/jobs/html_css_typescript_tailwind_frontend-development_web-development_react-js_git_github_twitter-bootstrap_javascript_nextjs/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    jobs = []
    for project_row in soup.select(".JobSearchCard-item"):
        print('---------==MAIN==LOOP---------------')
        title = project_row.select_one(".JobSearchCard-primary-heading-link")
        if title:
            title = title.get_text(strip=True)
        desc = project_row.select_one(".JobSearchCard-primary-description")
        if desc:
            desc = desc.get_text(strip=True)
        price = project_row.select_one(".JobSearchCard-primary-price")
        if price:
            price = price.get_text(strip=True)
        bidNum = project_row.select_one(".JobSearchCard-secondary-entry")
        if bidNum:
            bidNum = bidNum.get_text(strip=True)
        bidNow = project_row.select_one(".JobSearchCard-ctas-btn")
        if bidNow:
            bidNow = bidNow.get('href')

        jobs.append({
            "title": title,
            "desc": desc,
            "price": price,
            "bid": bidNow,
            "bidNum": bidNum,
        })

    new_jobs = []
    for job in jobs:
        job_url = f"https://www.freelancer.com{job['bid']}"
        if job_url not in sent_jobs:
            print('---------OUTTTTTTTT---------------')
            deposit = False
            payment = False
            secondScrap = requests.get(job_url)
            secondSoup = BeautifulSoup(secondScrap.text, "html.parser")
            time = secondSoup.select_one(
                ".PageProjectViewLogout-projectInfo-label-deliveryInfo-relativeTime")

            if time:
                time = time.get_text(strip=True)
                print("time:", time)

            project_row = secondSoup.select(
                ".PageProjectViewLogout-detail-reputation-verified-list-item")
            for jobdata in project_row:
                print('---------IN LOOP---------------')
                final = jobdata.get('data-qtsb-label')
                if final == 'deposit-made':
                    deposit = True
                if final == 'payment-verified':
                    payment = True
            job['deposit'] = deposit
            job['payment'] = payment
            job['time'] = time
            new_jobs.append(job)
            sent_jobs.add(job_url)

    if new_jobs:
        chat_id = os.getenv('CHAT_ID')
        for job in new_jobs:
            message = generate_message(job)
            try:
                if job.get('payment') is True:
                    print('PAYMENT Received-------', job)
                    await bot.send_message(chat_id=chat_id,
                                           text=message,
                                           disable_web_page_preview=True)
                sent_jobs.add(f"https://www.freelancer.com/{job['bid']}")
            except Exception as e:
                print(f"Error sending message: {e}")
        save_sent_jobs(sent_jobs)


async def main():
    try:
        while True:
            await scrape_and_send_jobs()
            await asyncio.sleep(30)
            print('New Check')
    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
    app.run(debug=True)  # Add this line to run the Flask app


@app.route('/')
def home():
    return jsonify(message='Freelancer Bot Server')
