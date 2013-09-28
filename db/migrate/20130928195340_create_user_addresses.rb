class CreateUserAddresses < ActiveRecord::Migration
  def change
    create_table :user_addresses do |t|
      t.string :address
      t.string :postal_code
      t.string :city
      t.string :country
      t.references :user

      t.timestamps
    end
  end
end
