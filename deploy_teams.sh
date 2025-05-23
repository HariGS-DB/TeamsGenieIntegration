cd appManifest
mkdir -p bin
zip bin/genie-teams.zip ./*
teamsapp install --file-path bin/genie-teams.zip