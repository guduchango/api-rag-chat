# Conversational RAG API for Product Catalogs

This project is a complete, cloud-native API that uses a **Retrieval-Augmented Generation (RAG)** architecture to answer user questions based on a product catalog. It's built with a modern Python stack and deployed entirely on Google Cloud Platform using Infrastructure as Code.

This API can:
- Ingest product data from a CSV file.
- Perform semantic searches to find relevant products.
- Maintain conversational memory for follow-up questions.
- Differentiate between product searches and simple chitchat.



## ✨ Features

- **FastAPI Backend:** A robust and modern API framework.
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
- [Terraform CLI](https://developer.hashicorp.com/terraform/tutorials/gcp-get-started/install-cli)
- [Google Cloud SDK (gcloud)](https://cloud.google.com/sdk/docs/install)
- Python 3.10 or 3.11
- A Google Cloud Project with billing enabled.

###  локальный Setup (Local Development)

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-name>
    ```

2.  **Create Service Account Key:**
    - Go to your GCP project's **IAM > Service Accounts** page.
    - Find the `api-rag-sa` service account.
    - Go to the **Keys** tab, click **Add Key > Create new key**, and download the JSON file.
    - Move the downloaded file to the project root and rename it to `gcp-credentials.json`.

3.  **Create `.env` file:**
    Create a file named `.env` in the project root and populate it with your local and GCP configuration. Use the `env.example` as a template.

    ```
    # .env - Local Development Environment Variables

    # --- GCP ---
    GCP_PROJECT_ID="your-gcp-project-id"
    GOOGLE_CLOUD_PROJECT="your-gcp-project-id"

    # --- Local Database (Docker) ---
    DB_USER="rag_user"
    DB_PASSWORD="testpassword"
    DB_HOST="db"
    DB_PORT="5432"
    DB_NAME="rag_db"
    ```

4.  **Add credentials to `.gitignore`:**
    Make sure your `.gitignore` file prevents your credentials from being committed:
    ```
    .env
    gcp-credentials.json
    __pycache__/
    *.pyc
    ```

5.  **Run the application:**
    Use Docker Compose to build and run the entire local environment with a single command:
    ```bash
    docker-compose up --build
    ```
    The API will be available at `http://127.0.0.1:8000`.

### ☁️ Deployment to Google Cloud

1.  **Configure Terraform:**
    - Create a file named `terraform.tfvars` and add your GCP project and billing information:
      ```tfvars
      gcp_project_id      = "your-gcp-project-id"
      gcp_billing_account = "XXXXXX-XXXXXX-XXXXXX"
      ```

2.  **Deploy Infrastructure:**
    Initialize and apply the Terraform configuration. This will build all the required cloud resources.
    ```bash
    terraform init
    terraform apply
    ```

3.  **Build and Deploy the Application:**
    - Authenticate Docker with GCP:
      ```bash
      gcloud auth configure-docker us-central1-docker.pkg.dev
      ```
    - Build the Docker image:
      ```bash
      docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/api-rag-repo/rag-api:v1 .
      ```
    - Push the image to Artifact Registry:
      ```bash
      docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/api-rag-repo/rag-api:v1
      ```
    - Deploy the image to Cloud Run:
      ```bash
      gcloud run deploy api-rag-service \
        --image=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/api-rag-repo/rag-api:v1 \
        --region=us-central1
      ```

##  API Usage

The API provides interactive documentation via Swagger UI. Once the service is running (locally or in the cloud), navigate to `/docs`.

### Example: Upload CSV

Upload a product catalog to be ingested into the vector database.

```bash
curl -X POST "[http://127.0.0.1:8000/api/upload-csv](http://127.0.0.1:8000/api/upload-csv)" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@./path/to/your/flipkart_ecommerce_sample.csv;type=text/csv"
```

### Example: Generate Prompt

Ask a question and get a RAG-generated prompt.

```bash
curl -X POST "[http://127.0.0.1:8000/api/generate-prompt?k=2](http://127.0.0.1:8000/api/generate-prompt?k=2)" \
  -H "accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user@example.com",
    "question": "shampoo for dogs"
  }'
```