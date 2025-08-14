## Cloning

Clone the repository:

```bash
git clone https://github.com/chungchihhan/calm.git
```

Navigate to the project directory:

```bash
cd calm
```

## Virtual Environment

Create a virtual environment:

```bash
python3 -m venv venv
```

Activate the virtual environment:

```bash
source venv/bin/activate
```

## Installation

Install the required packages using `pip`:

```bash
pip install -e .
```

## Configuration

Before using the tool, you need to set up your Google Calendar credentials. Follow these steps:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Navigate to "APIs & Services" > "Credentials".
4. Click on "Create Credentials" and select "OAuth client ID".
5. Configure the consent screen and select "Desktop app" as the application type.
6. Download the `credentials.json` file and copy it.
7. Run the following command to authenticate:

```bash
calm
```

8. Follow the prompts to authenticate with your Google account and save the credentials.
9. The credentials will be saved in `~/.calm/credentials.json` and the token in `~/.calm/token.json`.
10. If you need to reset the tokens, you can run:

```bash
calm configure reset
```

11. If you want to sign in again with oauth, you can run:

```bash
calm configure oauth
```

## Usage

You can use the `calm` command to manage your Google Calendar events. Here are some common commands:

- List today's events:

  ```bash
  calm today
  ```

- List events for tomorrow:

  ```bash
  calm tomorrow
  ```

- List events for this week:

  ```bash
  calm week
  ```

- List events for a specific date:

  ```bash
  calm date 2023-10-01
  ```
