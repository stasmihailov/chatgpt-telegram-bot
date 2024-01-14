gcloud functions deploy chatgpt-tg-bot \
  --runtime=python311 \
  --region=europe-west3 \
  --source=./chatgpt-tgbot/ \
  --entry-point=generate_images \
  --env-vars-file .env.yaml \
  --trigger-http \
  --allow-unauthenticated
