# AI Agents A-Z No-Code Tools (Community Edition)

Video editing tools to use with no-code tools like n8n, Zapier, and Make. Brought to you by [AI Agents A-Z](https://www.youtube.com/@aiagentsaz).

## [📚 Join our Skool community for the premium edition of the server and other premium content](https://www.skool.com/ai-agents-az/about)

[Watch the YouTube video featuring this project](https://www.youtube.com/watch?v=1-UuldAM6fQ)

### Be part of a growing community and help us create more content like this

# Starting the project

## Using Docker

```
docker run --rm -p 8000:8000 -it gyoridavid/ai-agents-no-code-tools:latest
```

If you have an NVidia GPU and have the [Cuda Toolkit](https://developer.nvidia.com/cuda-toolkit) installed, you can run the server with GPU support

```
docker run --rm --gpus=all -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=all -p 8000:8000 -it gyoridavid/ai-agents-no-code-tools:latest-cuda
```

## With python

1. Clone the repository
2. Create a virtual environment
   ```bash
   python -m venv venv
   ```
3. Activate the virtual environment
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```
4. Install the dependencies
   ```bash
   pip install -r requirements.txt
   ```
5. Run the application
   ```bash
   fastapi dev server.py --host 0.0.0.0
   ```

# Documentation

After starting the project, you can access the documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

# Contributing

While PRs are welcome, please note that due to the nature of the project, I may not be able to review them in a timely manner. If you have any questions or suggestions, feel free to open an issue.

# License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
