if [ ! -s ./initial_setup_marker.kf ]; then
  echo "Not skipping initial setup..."
  ./initial_setup.sh
fi
python ./generate_jobs_from_json.py
