class CreateEmergencyContacts < ActiveRecord::Migration
  def change
    create_table :emergency_contacts do |t|
      t.string :name
      t.string :relation
      t.string :phone_number
      t.text :remarks
      t.references :user, index: true

      t.timestamps
    end
  end
end
