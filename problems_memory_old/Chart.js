Feedback from previous attempts:
- This project requires Node.js 18 or higher
- Select a Compatible Base Image:

    Use a Docker base image with Node.js >= 18.12 to meet the project’s requirements immediately, avoiding the need for manual upgrades. For instance, node:18-slim instead of node:16-slim.

- Install pnpm Directly:

    After setting a compatible base image, install pnpm directly using npm install -g pnpm as a separate Docker layer to simplify dependency installation and reduce errors.

- Avoid nvm in Docker:

    Since Docker allows full control over the Node version in the image, avoid using nvm in favor of directly specifying the correct Node version in the Dockerfile.
