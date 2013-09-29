class AddRememberAddressToUsers < ActiveRecord::Migration
  def change
    add_column :users, :remember_address, :boolean
  end
end
