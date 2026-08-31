import nox


@nox.session
def tests(session):
    session.install(".[flask,django]", "pytest")
    session.run("pytest", "--ignore=tests/browser")


@nox.session
def browser(session):
    session.install(".[flask,django]", "pytest", "pytest-playwright")
    session.run("playwright", "install", "--with-deps", "chromium")
    session.run(
        "pytest",
        "tests/browser",
        "--browser=chromium",
        "--tracing=retain-on-failure",
    )
