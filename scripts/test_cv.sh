#!/bin/bash
API=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d'=' -f2)
CTOKEN=$(curl -s -X POST "$API/api/auth/login" -H "Content-Type: application/json" -d '{"email":"lucas.martin@email.fr","password":"Demo1234!"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
echo "GET CV:"
curl -s "$API/api/cv" -H "Authorization: Bearer $CTOKEN" | head -c 250
echo ""
echo "PUT CV:"
curl -s -X PUT "$API/api/cv" -H "Authorization: Bearer $CTOKEN" -H "Content-Type: application/json" -d @/app/scripts/cv_sample.json | head -c 250
echo ""
echo "PDF export:"
curl -s "$API/api/cv/export?template=modern" -H "Authorization: Bearer $CTOKEN" -o /tmp/cv.pdf -w "HTTP %{http_code} bytes %{size_download}\n"
file /tmp/cv.pdf
echo "AI improve test:"
curl -s -X POST "$API/api/cv/ai/improve" -H "Authorization: Bearer $CTOKEN" -H "Content-Type: application/json" -d '{"text":"je veux travailler dans linfo"}' | head -c 400
echo ""
