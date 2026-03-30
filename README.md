# Everett Little League

## Overview

Everett Little League is a non-profit organization that provides youth baseball and softball programs for children in the Everett, WA area.

This repository is the static site for Everett Little League code projects.

## Projects

### Snack Shack Signup Genius Banner

The Snack Shack Signup Genius Banner is a simple banner that displays the volunteer status for our snack shacks and a link to the Signup Genius registration page.

The banner is displayed on the top of the page and is a fixed position. It is updated every 15 minutes using GitHub Actions and the SignUpGenius API.

The public "Sign Up" button link is driven by the GitHub Actions repository variable `SIGNUPGENIUS_SIGNUP_URL`, so the league can switch seasons without changing code.

Current 2026 spring signup page: https://www.signupgenius.com/go/5080C44AEAB2EAAFF2-62435346-evll#/
