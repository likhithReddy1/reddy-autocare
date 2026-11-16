# Terraform deployment notes

This project is developed locally first. Azure deployment is intentionally a separate milestone.

The frontend is static and can be hosted on Azure Static Web Apps Free. The Python FastAPI backend and PostgreSQL database need their own hosting and database decisions. Do not deploy only the frontend and assume authentication/database features are live.

Before adding Terraform resources:
1. Confirm the Azure subscription owner has authorized use of the subscription.
2. Check the subscription offer, spending limits and available quotas.
3. Choose a backend host and PostgreSQL provider.
4. Keep all secrets out of Terraform state and Git.
5. Review pricing for every resource before `terraform apply`.

We will add the final Terraform configuration once the local app and database are tested.
