class AddRememberEmergencyContactsToUsers < ActiveRecord::Migration
  def change
    add_column :users, :remember_emergency_contacts, :boolean
  end
end
