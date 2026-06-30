# Homey GPT Assistant

[![Support me on Patreon](https://img.shields.io/badge/Patreon-Support%20my%20work-FF424D?style=flat&logo=patreon&logoColor=white)](https://www.patreon.com/AndersBjarby)

A Flask web app that lets you control an Athom Homey smart home through natural-language conversation. It reads your devices from the Homey API, hands them to GPT as context, and turns chat (or voice) commands into device actions.

## Features

- Chat interface for controlling smart-home devices in plain language
- Live device list and device cards pulled from the Homey API
- Voice page and user preferences
- Per-session conversation history

## Setup

Configure a `.env` file (see `.env.example`) with your `HOMEY_IP`, `HOMEY_API_KEY`, `OPENAI_API_KEY`, and a Flask `SECRET_KEY`.

```bash
cd home-automation
pip install -r requirements.txt
python run.py
```

Starts the Flask development server.

## Tech

Flask, OpenAI, Homey local API.
