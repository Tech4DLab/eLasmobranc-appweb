# 🌐 Web Application Overview

This application represents the integration and culmination of multiple prior tasks within the eLasmobranc project, including dataset construction and the development of artificial intelligence models. It provides a functional pipeline for the automatic analysis of large image collections, enabling elasmobranch detection, multi-level taxonomic classification and automated statistical reporting.

## 🏗️ 🐳 How to Run the Application

<p>
  <a href="https://drive.google.com/file/d/1s8yThPNy3RuZXzSMmp-3fmvVOnlRm_hC/view?usp=sharing">
    <img src="https://img.shields.io/badge/🧩 Example Dataset-F54927?style=for-the-badge&logoColor=white" />
  </a>
</p>

This application is distributed as ready-to-use Docker images. You do **not** need to install Python or any dependencies locally.

We provide both CPU and GPU implementations: the CPU version ensures broad compatibility across systems, while the GPU version enables faster inference for analyses but requires an NVIDIA GPU with proper driver.

**✅ Requirements**

You only need:
- **Docker Desktop** (Windows / macOS) or **Docker Engine** (Linux)
```bash
docker --version # verify Docker is installed
```

**🖥️ Run on CPU**

```bash
docker pull ibevias/elasmobranc:appcpu  # download CPU image
docker run -d -p 8000:7000 --name elasmobranc_app ibevias/elasmobranc:appcpu
```

**🖥️ Run on GPU**

```bash
docker pull ibevias/elasmobranc:appgpu  # download GPU image
docker run -d --gpus all -p 8000:7000 --name elasmobranc_app ibevias/elasmobranc:appgpu
```

**Open in Your Browser**
http://localhost:8000   # use a different port if 8000 is busy modifying the first port number in the `docker run` command.

**Stop the Application** 
```bash
docker stop elasmobranc_app
```

## 🏗️ System Architecture

The application follows a client-server architecture. Users interact with a responsive frontend built with **HTML**, **JavaScript** and **CSS**, structured into two main views: a landing page for data upload and a results page for visualization and analysis.

The backend is implemented in Python using the **Django framework**, which centralizes the application logic and handles request routing, view management and basic security mechanisms. Communication between frontend and backend is performed via HTTP requests through a **REST-style API**.

<p align="center">
  <img src="images/flujo.png" width="1000">
</p>

## 🏗️ Application Features

The web application capabilities is organized into three main components, corresponding to the system’s functional views: the landing page, the results page, and the PDF report.

### 🏠 Landing Page

The landing page serves as the user’s entry point to the system and is primarily dedicated to data submission for automatic image processing. Its central element is an upload form that allows users to provide a compressed ZIP file containing the images to be analyzed and, optionally, an Excel file with associated metadata.

To support correct usage, the page includes brief instructions guiding users through the data upload process. In addition to its core functionality, the landing page provides educational resources, including access to an image acquisition protocol and a link to an online book with background information on the target species.

<p align="center">
  <img src="images/inicio.PNG" width="900">
</p>

### 📊 Results Page

The results page is loaded once server-side processing is complete and focuses on interactive visualization of the analysis. A PDF export button is displayed at the top, allowing users to download the full report. First, model outputs are presented as taxonomic distribution charts, enabling comparison across different hierarchical levels.

<p align="center">
  <img src="images/g_resultados.PNG" width="700">
</p>

Next, a temporal analysis per species is provided at both yearly and monthly scales, highlighting observation patterns and facilitating comparison between classes. A geographical analysis follows, showing country-level distributions together with a detailed breakdown across Spanish autonomous communities for localized interpretation.

<p align="center">
  <img src="images/g_temporal.PNG" width="600">
  <img src="images/g_espacial.PNG" width="600">
</p>

Finally, a dedicated section displays individual elasmobranch detections along with model predictions and associated metadata. An additional block groups non-elasmobranch images to support manual review.

<p align="center">
  <img src="images/g_datos.png" width="600">
  <br>
  <img src="images/g_datosN.png" width="200">
</p>

### 📄 PDF Report

The PDF report summarizes the analysis results, reproducing the main visualizations from the Results Page. Furthemore, provides a static summary of the analysis, including key visualizations, dataset identification, statistical highlights (image count, detected classes, most frequent species, Shannon diversity index, and country distribution) and a final table listing all detected elasmobranchs with their taxonomic labels.

👉 **Example report**: <a href="Sample_PDF.pdf" target="_blank">PDF report</a>

## 🤝 Acknowledgments

This research was funded by the eLasmobranc project, which is developed with the collaboration of the Biodiversity Foundation of the Ministry for Ecological Transition and the Demographic Challenge, through the Pleamar Programme, and is co-financed by the European Union through the European Maritime, Fisheries and Aquaculture Fund.
