#!/usr/bin/env bash
# Deploy via SAM, resolving the shared Cognito app client at deploy time
# instead of baking its ID into samconfig.toml. Cognito assigns a fresh
# client_id whenever the app client is recreated, so a hardcoded value goes
# stale silently (login starts failing with no code change on this side);
# reading it from the shared-auth stack's own outputs means it can't drift.
set -euo pipefail
cd "$(dirname "$0")/.."

AUTH_STACK="${AUTH_STACK:-dtcdev-shared-auth}"
auth_output() {
  aws cloudformation describe-stacks --region us-east-1 --stack-name "$AUTH_STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
AUTH_CLIENT_ID="${AUTH_CLIENT_ID:-$(auth_output DataQnAClientId)}"
AUTH_ISSUER="${AUTH_ISSUER:-$(auth_output IssuerUrl)}"
AUTH_JWKS_URL="${AUTH_JWKS_URL:-$(auth_output JwksUrl)}"

sam deploy --config-env sandbox --parameter-overrides \
  DomainName=qna.dtcdev.click \
  DomainCertificateArn=arn:aws:acm:eu-west-1:817685572750:certificate/da5101db-666f-49da-a76b-e2c781afdd6b \
  HostedZoneId=Z05963572WVWFHDQZH5NE \
  AuthBaseUrl=https://auth.dtcdev.click \
  AuthClientId="$AUTH_CLIENT_ID" \
  AuthIssuer="$AUTH_ISSUER" \
  AuthJwksUrl="$AUTH_JWKS_URL" \
  RootAdmin=alexey@datatalks.club \
  "$@"
