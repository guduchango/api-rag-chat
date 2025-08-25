# Conversational RAG API for Product Catalogs

This project is a complete, cloud-native API that uses a **Retrieval-Augmented Generation (RAG)** architecture to answer user questions based on a product catalog. It's built with a modern Python stack and deployed entirely on Google Cloud Platform using Infrastructure as Code.

This API can:
- Ingest product data from a CSV file.
- Perform semantic searches to find relevant products.
- Maintain conversational memory for follow-up questions.
- Differentiate between product searches and simple chitchat.

## ✨ Features

- **FastAPI Backend:** A robust and modern API framework.
- **Modern Dependency Management:** Project dependencies and virtual environments are managed with **Poetry**.
- **Automated Code Quality:** Code formatting and linting are enforced automatically before each commit using **pre-commit** with `black` and `ruff`.
- **Cloud-Native Stack:** Runs on Google Cloud Run and connects to a managed Cloud SQL database.
- **Vector Database:** Uses PostgreSQL with the `pg_vector` extension for efficient similarity searches.
- **Cloud AI Models:** Leverages Google's Vertex AI for state-of-the-art text embeddings.
- **Conversational Memory:** Remembers the last 3 turns of a conversation for each user session.
- **Infrastructure as Code (IaC):** The entire cloud infrastructure is defined and managed with **Terraform**.
- **Containerized Development:** A full local development environment is orchestrated with **Docker Compose**.

## 🏛️ Architecture

The application follows a decoupled, service-based architecture:

1.  **Orchestrator (FastAPI on Cloud Run):** A serverless container that hosts the Python application logic. It handles user requests, manages conversation state, and orchestrates calls to other services.
2.  **Vector Store (Cloud SQL for PostgreSQL):** A managed database instance where product information and its corresponding vector embeddings are stored using the `pg_vector` extension.
3.  **Embedding Service (Vertex AI):** The `textembedding-gecko@003` model is called via its API to convert product descriptions and user questions into vector embeddings.
4.  **Secure Configuration:** Database passwords and other secrets are managed securely using **Google Secret Manager**.

## 🚀 Getting Started

### Prerequisites

- [Docker & Docker Compose](https://www.docker.com/products/docker-desktop/)
- [Poetry](https://python-poetry.org/docs/#installation)
- Python >=3.12
- [Terraform CLI](https://developer.hashicorp.com/terraform/tutorials/gcp-get-started/install-cli)
- [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install)
- A Google Cloud Project with billing enabled.

### Local Setup

#### Method 1: Running with Docker (Recommended)

This is the easiest way to get started, as it handles all dependencies within a container.

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Configure GCP Credentials:**
    - Create a Service Account key as a JSON file and save it in the project root as `gcp-credentials.json`.
    - **Important:** Make sure `gcp-credentials.json` and `.env` are listed in your `.gitignore` file to avoid committing secrets.

3.  **Create `.env` file:**
    Copy the `env.example` file to a new file named `.env` and fill in the values for your local and GCP setup.

4.  **Run the application:**
    Use Docker Compose to build and run the entire local stack (API + Database). The command now uses `Dockerfile.dev` which automatically installs dependencies with Poetry.
    ```bash
    docker-compose up --build
    ```
    The API will be available at `http://127.0.0.1:8000/docs`.

#### Method 2: Running Locally with Poetry (Without Docker)

Use this method if you prefer to run the Python application directly on your machine.

1.  **Complete Steps 1-3** from the Docker method above (Clone, Credentials, `.env`).

2.  **Install Dependencies:**
    Navigate to the project root and let Poetry install the required dependencies and create a virtual environment.
    ```bash
    poetry install
    ```

3.  **Activate the Virtual Environment:**
    Run your commands inside the virtual environment managed by Poetry.
    ```bash
    poetry shell
    ```

4.  **Install pre-commit hooks:**
    Activate the automated code quality checks for your local repository.
    ```bash
    pre-commit install
    ```

5.  **Run the API:**
    Start the Uvicorn server.
    ```bash
    uvicorn src.main:app --reload
    ```

### ☁️ Deployment to Google Cloud

The deployment process uses the production-optimized `Dockerfile`.

1.  **Configure Terraform:**
    - Create a file named `terraform.tfvars` and add your GCP project and billing information.

2.  **Deploy Infrastructure:**
    ```bash
    terraform init
    terraform apply
    ```

3.  **Build, Push, and Deploy the Application:**
    - Authenticate Docker with GCP:
      ```bash
      gcloud auth configure-docker us-central1-docker.pkg.dev
      ```
    - Build, push, and deploy using the provided names for your project, repository, and service.
      ```bash
      # Build
      docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/api-rag-repo/rag-api:v1 .

      # Push
      docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/api-rag-repo/rag-api:v1

      # Deploy
      gcloud run deploy api-rag-service \
        --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/api-rag-repo/rag-api:v1 \
        --region=us-central1
      ```

## API Usage

The API provides interactive documentation via Swagger UI. Once the service is running (locally or in the cloud), navigate to `/docs`.

### Example: Upload CSV

```bash
curl -X POST "[http://127.0.0.1:8000/api/upload-csv](http://127.0.0.1:8000/api/upload-csv)" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@./path/to/your/flipkart_ecommerce_sample.csv;type=text/csv"
  ```

### Example: Generate Prompt

```bash
curl -X POST "[http://127.0.0.1:8000/api/generate-prompt?k=2](http://127.0.0.1:8000/api/generate-prompt?k=2)" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user@example.com",
    "question": "shampoo for dogs"
  }'
  ```