class CreateMedicalDetails < ActiveRecord::Migration
  def change
    create_table :medical_details do |t|
      t.string :name
      t.string :type
      t.text :description
      t.references :user

      t.timestamps
    end
  end
end
