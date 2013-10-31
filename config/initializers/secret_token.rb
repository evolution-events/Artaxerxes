# Be sure to restart your server when you modify this file.

# Your secret key is used for verifying the integrity of signed cookies.
# If you change this key, all old signed cookies will become invalid!

# Make sure the secret is at least 30 characters and all random,
# no regular words or you'll be exposed to dictionary attacks.
# You can use `rake secret` to generate a secure secret key.

secret_token_file = Rails.root.join('config', 'secret_token')

unless File.file?(secret_token_file)
  File.write secret_token_file, SecureRandom.hex(64)
end

# Make sure your secret_key_base is kept private
# if you're sharing your code publicly.
Xerxes::Application.config.secret_key_base = File.read(secret_token_file).chomp
