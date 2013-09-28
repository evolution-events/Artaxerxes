class CreateUsers < ActiveRecord::Migration
  def change
    create_table :users do |t|
      t.string :first_name
      t.string :preposition
      t.string :last_name
      t.string :username
      t.date :birthdate
      t.string :phone_number
      t.string :email
      t.string :gender
      t.boolean :hide_last_name

      t.timestamps
    end
  end
end
