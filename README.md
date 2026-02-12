# 🌐 Web Application Overview

This application represents the integration and culmination of multiple prior tasks within the eLasmobranc project, including dataset construction and the development of artificial intelligence models. It provides a functional pipeline for the automatic analysis of large image collections, enabling elasmobranch detection, multi-level taxonomic classification and automated statistical reporting.

## 🏗️ System Architecture

The application follows a client-server architecture. Users interact with a responsive frontend built with **HTML**, **JavaScript** and **CSS**, structured into two main views: a landing page for data upload and a results page for visualization and analysis.

The backend is implemented in Python using the **Django framework**, which centralizes the application logic and handles request routing, view management and basic security mechanisms. Communication between frontend and backend is performed via HTTP requests through a **REST-style API**.

<p align="center">
  <img src="images/flujo.png" width="1000">
</p>
