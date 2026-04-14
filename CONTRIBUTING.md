# Contributing to AI Video Robot

Thank you for your interest in contributing to AI Video Robot! 🎉

## How to Contribute

### Reporting Bugs

If you find a bug, please open an issue with:
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)

### Suggesting Features

Feature requests are welcome! Please:
- Check existing issues first
- Describe the feature and use case
- Explain why it would be useful

### Submitting Pull Requests

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Follow existing code style
   - Add tests if applicable
   - Update documentation

4. **Test your changes**
   ```bash
   uv run python tests/test_ai_summary.py
   ```

5. **Commit with clear messages**
   ```bash
   git commit -m "feat: add new feature"
   ```

6. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/ai-video-robot.git
   cd ai-video-robot
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env with your API keys
   ```

4. **Run tests**
   ```bash
   uv run python tests/test_ai_summary.py
   ```

## Code Style

- Use UTF-8 encoding for all files
- Follow PEP 8 guidelines
- Add docstrings for functions and classes
- Keep functions focused and small
- Use meaningful variable names

## Commit Message Guidelines

We follow conventional commits:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Maintenance tasks

Examples:
```
feat: add support for YouTube videos
fix: resolve subtitle encoding issue
docs: update AI service setup guide
```

## Questions?

Feel free to open an issue for any questions or discussion!

## License

By contributing, you agree that your contributions will be licensed under CC BY-NC-SA 4.0.
